"""
xlsx_inspector.py

Deep ZIP-level inspection of .xlsx files to extract:
- All embedded media assets (PNG, JPG, EMF, WMF, etc.) from xl/media/
- Drawing anchor positions (row/col) from xl/drawings/drawing*.xml
- Drawing → media relationship mapping from xl/drawings/_rels/drawing*.xml.rels
- Worksheet → drawing relationship from xl/worksheets/_rels/sheet*.xml.rels
- OLE embedded objects from xl/embeddings/
- OMML (OfficeMath) content from worksheet cell XML

Returns a structured mapping: {row_num: {field_name: [AssetInfo]}}
"""

import os
import re
import io
import zipfile
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

logger = logging.getLogger("phd_app")

# Standard column index → question field name mapping
# Column 0=Question No, 1=Question Text, 2=Opt A, 3=Opt B, 4=Opt C, 5=Opt D, 6=Correct, 7=Marks
COL_IDX_TO_FIELD = {
    1: "question_text",
    2: "option_a",
    3: "option_b",
    4: "option_c",
    5: "option_d",
}

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".emf", ".wmf"}
VECTOR_EXTS = {".emf", ".wmf"}

# XML namespaces used in xlsx
NS = {
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "mc":  "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "x14": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main",
    "ss":  "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


@dataclass
class AssetInfo:
    """Represents a single embedded asset extracted from an Excel file."""
    asset_id: str           # unique id within this xlsx
    original_filename: str  # e.g. image1.emf
    original_ext: str       # e.g. .emf
    raw_bytes: bytes        # raw file bytes
    row: int                # 1-indexed Excel row
    col: int                # 0-indexed column
    field_name: str         # question_text / option_a / option_b / option_c / option_d
    is_vector: bool = False # True for EMF/WMF
    is_ole: bool = False    # True for OLE embedded objects
    omml_xml: Optional[str] = None  # OMML XML if found in OLE
    mime_type: str = "image/png"


@dataclass
class InspectionResult:
    """Full result of inspecting an xlsx file."""
    # row_assets[row_num][field_name] = list of AssetInfo
    row_assets: Dict[int, Dict[str, List[AssetInfo]]] = field(default_factory=dict)
    # omml_cells[row_num][field_name] = list of OMML XML strings
    omml_cells: Dict[int, Dict[str, List[str]]] = field(default_factory=dict)
    # Stats
    total_images: int = 0
    total_emf: int = 0
    total_wmf: int = 0
    total_ole: int = 0
    total_png_jpg: int = 0
    warnings: List[str] = field(default_factory=list)


def _parse_xml_safe(xml_bytes: bytes) -> Optional[ET.Element]:
    """Parse XML bytes safely, returning None on any parse error."""
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.debug(f"XML parse error (non-critical): {e}")
        return None


def _extract_col_from_anchor(anchor_elem: ET.Element) -> int:
    """Extract column index from a spreadsheetDrawing anchor element."""
    from_elem = anchor_elem.find("xdr:from", NS)
    if from_elem is not None:
        col_elem = from_elem.find("xdr:col", NS)
        if col_elem is not None and col_elem.text:
            try:
                return int(col_elem.text.strip())
            except ValueError:
                pass
    return 1  # default to question_text column


def _extract_row_from_anchor(anchor_elem: ET.Element) -> int:
    """Extract row index (0-based) from a spreadsheetDrawing anchor element."""
    from_elem = anchor_elem.find("xdr:from", NS)
    if from_elem is not None:
        row_elem = from_elem.find("xdr:row", NS)
        if row_elem is not None and row_elem.text:
            try:
                return int(row_elem.text.strip())  # 0-based in xlsx
            except ValueError:
                pass
    return 1  # default


def _field_from_col(col_idx: int, col_field_map: Optional[Dict[int, str]] = None) -> str:
    """Map column index to question field name."""
    if col_field_map and col_idx in col_field_map:
        candidate = col_field_map[col_idx]
        if candidate in COL_IDX_TO_FIELD.values():
            return candidate
    return COL_IDX_TO_FIELD.get(col_idx, "question_text")


def _mime_from_ext(ext: str) -> str:
    ext = ext.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".emf": "image/x-emf",
        ".wmf": "image/x-wmf",
    }
    return mime_map.get(ext, "application/octet-stream")


def inspect_xlsx(
    xlsx_path: str,
    col_field_map: Optional[Dict[int, str]] = None,
    max_asset_size_mb: float = 20.0
) -> InspectionResult:
    """
    Deep inspection of an xlsx file to extract all embedded assets.

    Args:
        xlsx_path: Path to the .xlsx file
        col_field_map: Optional mapping of column index → field name
        max_asset_size_mb: Maximum size per asset in MB (security limit)

    Returns:
        InspectionResult with all extracted assets mapped by row and field
    """
    result = InspectionResult()
    max_bytes = int(max_asset_size_mb * 1024 * 1024)

    if not os.path.exists(xlsx_path):
        result.warnings.append(f"File not found: {xlsx_path}")
        return result

    try:
        zf = zipfile.ZipFile(xlsx_path, 'r')
    except zipfile.BadZipFile as e:
        result.warnings.append(f"Not a valid xlsx ZIP: {e}")
        return result

    with zf:
        all_names = set(zf.namelist())

        # Step 1: Build media index: rId -> (filename, ext, bytes)
        media_bytes: Dict[str, Tuple[str, str, bytes]] = {}
        for name in all_names:
            if name.startswith("xl/media/"):
                fname = os.path.basename(name)
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_IMAGE_EXTS:
                    try:
                        raw = zf.read(name)
                        if len(raw) > max_bytes:
                            result.warnings.append(f"Asset {fname} exceeds size limit ({len(raw)//1024}KB), skipping.")
                            continue
                        # Key by filename for lookup
                        media_bytes[fname] = (fname, ext, raw)
                    except Exception as e:
                        result.warnings.append(f"Could not read media/{fname}: {e}")

        # Also index OLE embeddings
        ole_bytes: Dict[str, bytes] = {}
        for name in all_names:
            if name.startswith("xl/embeddings/"):
                fname = os.path.basename(name)
                try:
                    raw = zf.read(name)
                    if len(raw) <= max_bytes:
                        ole_bytes[fname] = raw
                except Exception as e:
                    result.warnings.append(f"Could not read embedding/{fname}: {e}")

        # Step 2: Parse drawing relationship files to map rId → media filename
        # xl/drawings/_rels/drawing*.xml.rels
        drawing_rel_map: Dict[str, Dict[str, str]] = {}  # drawing_name -> {rId: target}
        for name in all_names:
            if re.match(r"xl/drawings/_rels/drawing\d+\.xml\.rels", name):
                drawing_name = name.replace("_rels/", "").replace(".rels", "")
                try:
                    rels_xml = zf.read(name)
                    rels_root = _parse_xml_safe(rels_xml)
                    if rels_root is None:
                        continue
                    rid_map = {}
                    for rel_elem in rels_root:
                        rid = rel_elem.get("Id", "")
                        target = rel_elem.get("Target", "")
                        # Target is relative: ../media/image1.emf or ../embeddings/...
                        if rid and target:
                            rid_map[rid] = os.path.basename(target)
                    drawing_rel_map[drawing_name] = rid_map
                except Exception as e:
                    result.warnings.append(f"Could not parse drawing rels {name}: {e}")

        # Step 3: Parse worksheet relationship files to map drawing → sheet
        # xl/worksheets/_rels/sheet*.xml.rels
        sheet_to_drawings: Dict[str, List[str]] = {}  # sheet_xml_name -> [drawing_xml_names]
        for name in all_names:
            if re.match(r"xl/worksheets/_rels/sheet\d+\.xml\.rels", name):
                sheet_name = name.replace("_rels/", "").replace(".rels", "")
                try:
                    rels_xml = zf.read(name)
                    rels_root = _parse_xml_safe(rels_xml)
                    if rels_root is None:
                        continue
                    drawings = []
                    for rel_elem in rels_root:
                        rel_type = rel_elem.get("Type", "")
                        target = rel_elem.get("Target", "")
                        if "drawing" in rel_type.lower() and target:
                            # Normalize path
                            if target.startswith("../"):
                                target = "xl/" + target[3:]
                            elif not target.startswith("xl/"):
                                target = "xl/drawings/" + os.path.basename(target)
                            drawings.append(target)
                    sheet_to_drawings[sheet_name] = drawings
                except Exception as e:
                    result.warnings.append(f"Could not parse sheet rels {name}: {e}")

        # Step 4: Parse drawing XML files to get anchor→rId mappings
        # xl/drawings/drawing*.xml
        # Build: drawing_xml_name -> [{row, col, rId, type}]
        drawing_anchors: Dict[str, List[Dict]] = {}
        for name in all_names:
            if re.match(r"xl/drawings/drawing\d+\.xml$", name):
                try:
                    drawing_xml = zf.read(name)
                    drawing_root = _parse_xml_safe(drawing_xml)
                    if drawing_root is None:
                        continue
                    anchors = []
                    # Look for twoCellAnchor and oneCellAnchor
                    for anchor_tag in ["xdr:twoCellAnchor", "xdr:oneCellAnchor", "xdr:absoluteAnchor"]:
                        for anchor in drawing_root.findall(anchor_tag, NS):
                            row_0based = _extract_row_from_anchor(anchor)
                            col = _extract_col_from_anchor(anchor)
                            # Look for picture (rId reference)
                            pic = anchor.find(".//xdr:pic", NS)
                            graphicFrame = anchor.find(".//xdr:graphicFrame", NS)
                            sp = anchor.find(".//xdr:sp", NS)

                            rid = None
                            item_type = "image"

                            if pic is not None:
                                blipFill = pic.find(".//a:blipFill", NS)
                                if blipFill is not None:
                                    blip = blipFill.find("a:blip", NS)
                                    if blip is not None:
                                        rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                                item_type = "image"
                            elif graphicFrame is not None:
                                # Could be OLE or chart
                                graphic = graphicFrame.find(".//a:graphic", NS)
                                if graphic is not None:
                                    graphicData = graphic.find("a:graphicData", NS)
                                    if graphicData is not None:
                                        uri = graphicData.get("uri", "")
                                        if "oleObject" in uri or "chart" in uri:
                                            item_type = "ole"
                                            # Try to get rId from oleObject
                                            for child in graphicData:
                                                r = child.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                                                if r:
                                                    rid = r
                                                    break

                            if rid:
                                anchors.append({
                                    "row_0based": row_0based,
                                    "col": col,
                                    "rId": rid,
                                    "type": item_type
                                })

                    drawing_anchors[name] = anchors
                except Exception as e:
                    result.warnings.append(f"Could not parse drawing XML {name}: {e}")

        # Step 5: Build the final mapping
        # For each sheet, find its drawings, then for each anchor resolve the asset
        # We assume the first/active sheet is the relevant one

        # Find the active sheet (first sheet that has drawings linked)
        # Simplified: use all sheets, they all contribute to row_assets
        asset_counter = 0
        processed_anchors = []

        for sheet_xml, drawing_list in sheet_to_drawings.items():
            for drawing_xml_name in drawing_list:
                rid_to_media = drawing_rel_map.get(drawing_xml_name, {})
                anchors = drawing_anchors.get(drawing_xml_name, [])

                for anchor in anchors:
                    rid = anchor["rId"]
                    row_0based = anchor["row_0based"]
                    col = anchor["col"]
                    item_type = anchor["type"]

                    # Convert 0-based anchor row to 1-indexed Excel data row
                    # Row 0 in anchor = header row (row 1 in Excel = row index 0 in pandas)
                    # Data starts at anchor row 1 = Excel row 2 = pandas index 0
                    # So: data_row = row_0based (already 0-based, header is row 0)
                    # pandas index = row_0based - 1 (since row 0 = header)
                    # Excel row number = row_0based + 1
                    excel_row = row_0based + 1  # 1-indexed Excel row number

                    field_name = _field_from_col(col, col_field_map)

                    media_fname = rid_to_media.get(rid, "")
                    if not media_fname:
                        result.warnings.append(
                            f"Drawing anchor at row={excel_row}, col={col} has rId={rid} but no media target found."
                        )
                        continue

                    asset_counter += 1
                    asset_id = f"asset_{asset_counter}"

                    if item_type == "ole" and media_fname in ole_bytes:
                        raw = ole_bytes[media_fname]
                        info = AssetInfo(
                            asset_id=asset_id,
                            original_filename=media_fname,
                            original_ext=os.path.splitext(media_fname)[1].lower(),
                            raw_bytes=raw,
                            row=excel_row,
                            col=col,
                            field_name=field_name,
                            is_vector=False,
                            is_ole=True,
                            mime_type="application/vnd.openxmlformats-officedocument.oleObject"
                        )
                        result.total_ole += 1
                    elif media_fname in media_bytes:
                        fname, ext, raw = media_bytes[media_fname]
                        is_vec = ext in VECTOR_EXTS
                        info = AssetInfo(
                            asset_id=asset_id,
                            original_filename=fname,
                            original_ext=ext,
                            raw_bytes=raw,
                            row=excel_row,
                            col=col,
                            field_name=field_name,
                            is_vector=is_vec,
                            is_ole=False,
                            mime_type=_mime_from_ext(ext)
                        )
                        if ext == ".emf":
                            result.total_emf += 1
                        elif ext == ".wmf":
                            result.total_wmf += 1
                        else:
                            result.total_png_jpg += 1
                    else:
                        result.warnings.append(
                            f"Media '{media_fname}' referenced by anchor at row={excel_row} not found in xl/media/"
                        )
                        continue

                    result.total_images += 1
                    if excel_row not in result.row_assets:
                        result.row_assets[excel_row] = {}
                    if field_name not in result.row_assets[excel_row]:
                        result.row_assets[excel_row][field_name] = []
                    result.row_assets[excel_row][field_name].append(info)
                    processed_anchors.append((excel_row, field_name))

        # Step 6: Fallback — if no drawing rels were found, try direct worksheet XML scan
        # This catches some xlsx files where drawings are embedded differently
        if not processed_anchors:
            _fallback_scan_worksheet_xml(zf, all_names, media_bytes, ole_bytes, result, col_field_map, max_bytes)

        # Step 7: Log inspection summary
        logger.info(
            f"xlsx_inspector: found {result.total_images} assets "
            f"(PNG/JPG: {result.total_png_jpg}, EMF: {result.total_emf}, "
            f"WMF: {result.total_wmf}, OLE: {result.total_ole})"
        )

    return result


def _fallback_scan_worksheet_xml(
    zf: zipfile.ZipFile,
    all_names: set,
    media_bytes: dict,
    ole_bytes: dict,
    result: InspectionResult,
    col_field_map: Optional[Dict[int, str]],
    max_bytes: int
):
    """
    Fallback: scan worksheet XML directly for v:imagedata or a:blip references.
    Used when the standard drawing relationship chain doesn't resolve.
    """
    for name in all_names:
        if re.match(r"xl/worksheets/sheet\d+\.xml$", name):
            try:
                ws_xml = zf.read(name)
                # Simple regex scan for embed rIds in worksheet
                # This is a last-resort approach
                rids_in_ws = re.findall(r'r:embed="(rId\d+)"', ws_xml.decode("utf-8", errors="replace"))
                if rids_in_ws:
                    logger.debug(f"Fallback: found {len(rids_in_ws)} rId refs in {name}")
            except Exception:
                pass

    # If media files exist but no anchors found, assign them to rows sequentially
    # This is a heuristic last resort
    if media_bytes and not result.row_assets:
        result.warnings.append(
            "Could not resolve drawing anchors — images may be assigned to incorrect rows. "
            "Using sequential fallback assignment."
        )
        asset_counter = 0
        for fname, (orig_fname, ext, raw) in media_bytes.items():
            asset_counter += 1
            # Default: assign to row 2 (first data row), question_text field
            excel_row = asset_counter + 1
            field_name = "question_text"
            is_vec = ext in VECTOR_EXTS

            info = AssetInfo(
                asset_id=f"fallback_{asset_counter}",
                original_filename=orig_fname,
                original_ext=ext,
                raw_bytes=raw,
                row=excel_row,
                col=1,
                field_name=field_name,
                is_vector=is_vec,
                is_ole=False,
                mime_type=_mime_from_ext(ext)
            )
            result.total_images += 1
            if ext == ".emf":
                result.total_emf += 1
            elif ext == ".wmf":
                result.total_wmf += 1
            else:
                result.total_png_jpg += 1

            if excel_row not in result.row_assets:
                result.row_assets[excel_row] = {}
            if field_name not in result.row_assets[excel_row]:
                result.row_assets[excel_row][field_name] = []
            result.row_assets[excel_row][field_name].append(info)
