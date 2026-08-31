"""
import_pipeline.py

Main orchestrator for the Advanced Excel Question Import pipeline.

Integrates:
- xlsx_inspector: deep ZIP-level asset extraction
- vector_converter: EMF/WMF → PNG conversion
- ole_extractor: OLE/MathType object handling
- omml_converter: OMML → LaTeX conversion
- Standard pandas row parsing (existing logic)

Returns a structured AdvancedImportResult with per-question asset stats
and honest conversion status for admin review.
"""

import os
import io
import uuid
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.services.excel_import.xlsx_inspector import inspect_xlsx, AssetInfo, COL_IDX_TO_FIELD
from app.services.excel_import.vector_converter import convert_to_png, ConversionResult
from app.services.excel_import.ole_extractor import extract_ole_content
from app.services.excel_import.omml_converter import omml_to_latex

logger = logging.getLogger("phd_app")


@dataclass
class AssetImportStatus:
    """Status of a single asset conversion during import."""
    original_filename: str
    original_format: str
    field_name: str
    web_url: str            # Empty string if conversion failed
    status: str             # "success", "conversion_failed", "omml_converted", "skipped"
    method_used: str        # "wand", "pillow", "gdi32", "omml_latex", "failed"
    reason: str = ""        # Error reason if failed


@dataclass
class QuestionImportDetail:
    """Per-question import detail including all asset statuses."""
    question_no: int
    assets: List[AssetImportStatus] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AdvancedImportResult:
    """Full result of the advanced Excel import pipeline."""
    # Per-row question data ready for DB insert
    valid_rows: List[Dict] = field(default_factory=list)
    # Validation errors (same format as existing system)
    errors: List[Dict] = field(default_factory=list)
    # Asset stats
    asset_stats: Dict[str, int] = field(default_factory=dict)
    conversion_success: int = 0
    conversion_failed: int = 0
    omml_converted: int = 0
    total_rows_inspected: int = 0
    # Per-question details for admin display
    question_details: List[QuestionImportDetail] = field(default_factory=list)
    # Global warnings
    warnings: List[str] = field(default_factory=list)


def _sha8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_col_field_map(df_columns: list) -> Dict[int, str]:
    """
    Build column index → field name mapping from dataframe columns.
    Matches existing COLUMN_MAPPING logic from question_excel_utils.py.
    """
    from app.utils.question_excel_utils import COLUMN_MAPPING, normalize_question_column_name
    col_field_map = {}
    for idx, col in enumerate(df_columns):
        normalized = normalize_question_column_name(col)
        mapped = COLUMN_MAPPING.get(normalized, normalized)
        if mapped in ("question_text", "option_a", "option_b", "option_c", "option_d"):
            col_field_map[idx] = mapped
    return col_field_map


def _save_asset(
    asset: AssetInfo,
    batch_id: str,
    image_dir: str,
    original_dir: Optional[str] = None
) -> AssetImportStatus:
    """
    Process a single AssetInfo:
    1. If OLE → try extract_ole_content → get EMF/OMML
    2. If vector (EMF/WMF) → convert_to_png via Wand
    3. If raster (PNG/JPG) → convert_to_png via Pillow
    4. Return AssetImportStatus with honest success/failure
    """
    ext = asset.original_ext.lower()

    # Generate stable output filename
    content_hash = _sha8(asset.raw_bytes)
    png_filename = f"q_img_{batch_id}_r{asset.row}_{asset.field_name}_{content_hash}.png"
    png_path = os.path.join(image_dir, png_filename)
    web_url = f"/static/question_images/{png_filename}"

    # ── CASE 1: OLE object (MathType / Equation Editor) ──
    if asset.is_ole:
        ole_content = extract_ole_content(asset.raw_bytes)

        # Try OMML → LaTeX first
        if ole_content.omml_xml:
            latex = omml_to_latex(ole_content.omml_xml)
            if latex:
                return AssetImportStatus(
                    original_filename=asset.original_filename,
                    original_format=ext,
                    field_name=asset.field_name,
                    web_url="",           # No image URL — returns LaTeX string
                    status="omml_converted",
                    method_used="omml_latex",
                    reason=f"OMML → LaTeX: {latex[:80]}..."
                )

        # Try EMF/WMF preview from OLE
        if ole_content.preview_bytes and ole_content.preview_format:
            conv_result = convert_to_png(
                ole_content.preview_bytes,
                png_path,
                f".{ole_content.preview_format}",
                original_dir
            )
            if conv_result.success:
                return AssetImportStatus(
                    original_filename=asset.original_filename,
                    original_format=ext,
                    field_name=asset.field_name,
                    web_url=web_url,
                    status="success",
                    method_used=conv_result.method_used,
                    reason=f"OLE preview ({ole_content.preview_format}) → PNG"
                )

        # OLE extraction failed
        label = "MathType" if ole_content.mathtype_detected else (
            "EquationEditor" if ole_content.equation_editor_detected else "OLE"
        )
        return AssetImportStatus(
            original_filename=asset.original_filename,
            original_format=ext,
            field_name=asset.field_name,
            web_url="",
            status="conversion_failed",
            method_used="failed",
            reason=f"{label} object: {ole_content.error or 'No extractable preview found'}"
        )

    # ── CASE 2: Vector image (EMF / WMF) ──
    if asset.is_vector:
        conv_result = convert_to_png(asset.raw_bytes, png_path, ext, original_dir)
        if conv_result.success:
            return AssetImportStatus(
                original_filename=asset.original_filename,
                original_format=ext,
                field_name=asset.field_name,
                web_url=web_url,
                status="success",
                method_used=conv_result.method_used
            )
        else:
            return AssetImportStatus(
                original_filename=asset.original_filename,
                original_format=ext,
                field_name=asset.field_name,
                web_url="",
                status="conversion_failed",
                method_used="failed",
                reason=conv_result.error_reason
            )

    # ── CASE 3: Raster image (PNG / JPG / etc.) ──
    conv_result = convert_to_png(asset.raw_bytes, png_path, ext, original_dir)
    if conv_result.success:
        return AssetImportStatus(
            original_filename=asset.original_filename,
            original_format=ext,
            field_name=asset.field_name,
            web_url=web_url,
            status="success",
            method_used=conv_result.method_used
        )
    else:
        return AssetImportStatus(
            original_filename=asset.original_filename,
            original_format=ext,
            field_name=asset.field_name,
            web_url="",
            status="conversion_failed",
            method_used="failed",
            reason=conv_result.error_reason
        )


def run_advanced_import(
    excel_path: str,
    batch_id: str,
    image_dir: str,
    col_field_map: Optional[Dict[int, str]] = None,
    original_asset_dir: Optional[str] = None,
) -> AdvancedImportResult:
    """
    Full advanced import pipeline for an Excel question file.

    Args:
        excel_path: Path to the uploaded .xlsx file
        batch_id: Unique batch ID for this upload
        image_dir: Directory to save converted PNG images
        col_field_map: Optional column index → field name mapping
        original_asset_dir: If provided, original EMF/WMF files are preserved here

    Returns:
        AdvancedImportResult with parsed questions + asset conversion status
    """
    result = AdvancedImportResult()
    os.makedirs(image_dir, exist_ok=True)

    # ── Step 1: Load Excel with pandas (existing logic) ──
    try:
        df = pd.read_excel(excel_path, keep_default_na=False)
    except Exception as e:
        result.errors.append({
            "row": 0, "question_no": None,
            "error": f"Failed to read Excel: {str(e)}"
        })
        return result

    result.total_rows_inspected = len(df)

    # Normalize columns
    from app.utils.question_excel_utils import (
        COLUMN_MAPPING, normalize_question_column_name,
        validate_question_required_columns, parse_correct_option,
        parse_marks, clean_question_text, validate_question_row
    )

    normalized_cols = [normalize_question_column_name(c) for c in df.columns]
    mapped_cols = [COLUMN_MAPPING.get(col, col) for col in normalized_cols]
    df.columns = mapped_cols

    ok, missing = validate_question_required_columns(df.columns)
    if not ok:
        result.errors.append({
            "row": 0, "question_no": None,
            "error": f"Missing required columns: {', '.join(missing)}"
        })
        return result

    # Build col_field_map from the original (pre-normalized) column order
    if col_field_map is None:
        col_field_map = {}
        for idx, col in enumerate(df.columns):
            if col in ("question_text", "option_a", "option_b", "option_c", "option_d"):
                col_field_map[idx] = col

    # ── Step 2: Deep ZIP-level asset extraction ──
    logger.info(f"import_pipeline: Starting xlsx inspection for batch {batch_id}")
    inspection = inspect_xlsx(excel_path, col_field_map=col_field_map)
    result.warnings.extend(inspection.warnings)

    # Update stats
    result.asset_stats = {
        "PNG_JPG": inspection.total_png_jpg,
        "EMF": inspection.total_emf,
        "WMF": inspection.total_wmf,
        "OLE": inspection.total_ole,
        "TOTAL": inspection.total_images,
    }
    logger.info(
        f"import_pipeline: Found {inspection.total_images} assets — "
        f"PNG/JPG: {inspection.total_png_jpg}, EMF: {inspection.total_emf}, "
        f"WMF: {inspection.total_wmf}, OLE: {inspection.total_ole}"
    )

    # ── Step 3: Convert all extracted assets ──
    # row_converted[excel_row][field_name] = list of (web_url, omml_latex, status)
    row_converted: Dict[int, Dict[str, List[Tuple]]] = {}

    for excel_row, field_assets in inspection.row_assets.items():
        row_converted[excel_row] = {}
        for fld_name, asset_list in field_assets.items():
            row_converted[excel_row][fld_name] = []

            for asset in asset_list:
                asset_status = _save_asset(asset, batch_id, image_dir, original_asset_dir)

                # Track stats
                if asset_status.status == "success":
                    result.conversion_success += 1
                elif asset_status.status == "omml_converted":
                    result.omml_converted += 1
                elif asset_status.status == "conversion_failed":
                    result.conversion_failed += 1
                    result.warnings.append(
                        f"Row {excel_row}, field '{fld_name}': "
                        f"Asset '{asset.original_filename}' conversion failed — {asset_status.reason}"
                    )

                # Store result: (web_url or None, latex or None, status_obj)
                omml_latex = None
                if asset_status.status == "omml_converted" and asset_status.reason:
                    # Extract the LaTeX from the reason string
                    omml_latex = _extract_latex_from_reason(asset_status.reason)

                row_converted[excel_row][fld_name].append({
                    "web_url": asset_status.web_url,
                    "omml_latex": omml_latex,
                    "status": asset_status.status,
                    "filename": asset.original_filename,
                    "ext": asset.original_ext,
                })

    # ── Step 4: Assemble question rows ──
    seen_q_nos: set = set()

    for index, row in df.iterrows():
        row_number = index + 2  # Excel row number (1-indexed, row 1 = header)
        row_dict = row.to_dict()
        row_assets_converted = row_converted.get(row_number, {})

        # Build image tags and LaTeX injections per field
        def build_field_content(field_name: str) -> str:
            raw_text = clean_question_text(row_dict.get(field_name, ""))
            assets_for_field = row_assets_converted.get(field_name, [])

            parts = []
            if raw_text:
                parts.append(raw_text)

            for asset_data in assets_for_field:
                if asset_data["status"] == "success" and asset_data["web_url"]:
                    img_tag = (
                        f'<img src="{asset_data["web_url"]}" '
                        f'alt="{field_name} image" '
                        f'data-format="{asset_data["ext"].lstrip(".")}" />'
                    )
                    parts.append(img_tag)
                elif asset_data["status"] == "omml_converted" and asset_data["omml_latex"]:
                    parts.append(asset_data["omml_latex"])
                # conversion_failed: skip — don't add broken image tag

            return "\n".join(parts)

        # Determine primary image_path for the image_path DB column
        primary_image = None
        for fld in ("question_text", "option_a", "option_b", "option_c", "option_d"):
            fld_assets = row_assets_converted.get(fld, [])
            for a in fld_assets:
                if a["status"] == "success" and a["web_url"]:
                    primary_image = a["web_url"]
                    break
            if primary_image:
                break

        # Build image dict for validate_question_row compatibility
        row_imgs_for_validate = {
            fld: [a["web_url"] for a in assets if a["status"] == "success" and a["web_url"]]
            for fld, assets in row_assets_converted.items()
        }

        valid, err_msg, parsed_q_no = validate_question_row(
            row_dict, row_number, row_imgs_for_validate
        )

        if not valid:
            result.errors.append({
                "row": row_number,
                "question_no": parsed_q_no,
                "error": err_msg
            })
            continue

        if parsed_q_no in seen_q_nos:
            result.errors.append({
                "row": row_number,
                "question_no": parsed_q_no,
                "error": f"Duplicate question number '{parsed_q_no}' in this Excel file."
            })
            continue

        seen_q_nos.add(parsed_q_no)

        clean_row = {
            "question_no": parsed_q_no,
            "question_text": build_field_content("question_text"),
            "option_a": build_field_content("option_a"),
            "option_b": build_field_content("option_b"),
            "option_c": build_field_content("option_c"),
            "option_d": build_field_content("option_d"),
            "correct_option": parse_correct_option(row_dict.get("correct_option")),
            "marks": parse_marks(row_dict.get("marks")),
            "image_path": primary_image,
        }
        result.valid_rows.append(clean_row)

        # Build question detail for admin reporting
        detail = QuestionImportDetail(question_no=parsed_q_no)
        for fld, asset_list in row_assets_converted.items():
            for a in asset_list:
                detail.assets.append(AssetImportStatus(
                    original_filename=a["filename"],
                    original_format=a["ext"],
                    field_name=fld,
                    web_url=a["web_url"],
                    status=a["status"],
                    method_used="",
                ))
        result.question_details.append(detail)

    logger.info(
        f"import_pipeline: batch={batch_id} complete. "
        f"valid={len(result.valid_rows)}, errors={len(result.errors)}, "
        f"assets_ok={result.conversion_success}, assets_failed={result.conversion_failed}, "
        f"omml={result.omml_converted}"
    )

    return result


def _extract_latex_from_reason(reason: str) -> Optional[str]:
    """Extract LaTeX string from the reason field of an omml_converted AssetImportStatus."""
    prefix = "OMML → LaTeX: "
    if reason.startswith(prefix):
        latex = reason[len(prefix):]
        # Remove trailing ellipsis if truncated
        if latex.endswith("..."):
            latex = latex[:-3]
        return latex
    return None
