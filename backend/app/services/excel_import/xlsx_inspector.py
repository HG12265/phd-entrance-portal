"""
xlsx_inspector.py

Deep ZIP-level inspection of .xlsx files to extract:
- All embedded media assets (PNG, JPG, EMF, WMF, etc.) from xl/media/
- Standard DrawingML anchor positions (row/col) from xl/drawings/drawing*.xml
- VML Drawing anchor positions (row/col) from xl/drawings/vmlDrawing*.vml
- Drawing → media relationship mapping from xl/drawings/_rels/drawing*.xml.rels & vmlDrawing*.vml.rels
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
    row_assets: Dict[int, Dict[str, List[AssetInfo]]] = field(default_factory=dict)
    omml_cells: Dict[int, Dict[str, List[str]]] = field(default_factory=dict)
    total_images: int = 0
    total_emf: int = 0
    total_wmf: int = 0
    total_ole: int = 0
    total_png_jpg: int = 0
    warnings: List[str] = field(default_factory=list)


def _parse_xml_safe(xml_bytes: bytes) -> Optional[ET.Element]:
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.debug(f"XML parse error (non-critical): {e}")
        return None


def _extract_col_from_anchor(anchor_elem: ET.Element) -> int:
    from_elem = anchor_elem.find("xdr:from", NS)
    if from_elem is not None:
        col_elem = from_elem.find("xdr:col", NS)
        if col_elem is not None and col_elem.text:
            try:
                return int(col_elem.text.strip())
            except ValueError:
                pass
    return 1


def _extract_row_from_anchor(anchor_elem: ET.Element) -> int:
    from_elem = anchor_elem.find("xdr:from", NS)
    if from_elem is not None:
        row_elem = from_elem.find("xdr:row", NS)
        if row_elem is not None and row_elem.text:
            try:
                return int(row_elem.text.strip())
            except ValueError:
                pass
    return 1


def _field_from_col(col_idx: int, col_field_map: Optional[Dict[int, str]] = None) -> str:
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

        # Step 1: Index all media files from xl/media/
        media_bytes: Dict[str, Tuple[str, str, bytes]] = {}
        for name in all_names:
            if name.startswith("xl/media/"):
                fname = os.path.basename(name)
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_IMAGE_EXTS:
                    try:
                        raw = zf.read(name)
                        if len(raw) <= max_bytes:
                            media_bytes[fname] = (fname, ext, raw)
                    except Exception as e:
                        result.warnings.append(f"Could not read media/{fname}: {e}")

        # Index OLE embeddings
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

        # Step 2: Parse drawing relationship files (DrawingML + VML)
        drawing_rel_map: Dict[str, Dict[str, str]] = {}
        for name in all_names:
            if re.match(r"xl/drawings/_rels/(?:drawing|vmlDrawing)\d+\.(?:xml|vml)\.rels$", name):
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
                        if rid and target:
                            rid_map[rid] = os.path.basename(target)
                    drawing_rel_map[drawing_name] = rid_map
                except Exception as e:
                    result.warnings.append(f"Could not parse drawing rels {name}: {e}")

        # Step 3: Parse worksheet relationship files (drawing + vmlDrawing)
        sheet_to_drawings: Dict[str, List[str]] = {}
        for name in all_names:
            if re.match(r"xl/worksheets/_rels/sheet\d+\.xml\.rels$", name):
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
                        if ("drawing" in rel_type.lower() or "vmldrawing" in rel_type.lower()) and target:
                            if target.startswith("../"):
                                target = "xl/" + target[3:]
                            elif not target.startswith("xl/"):
                                target = "xl/drawings/" + os.path.basename(target)
                            drawings.append(target)
                    sheet_to_drawings[sheet_name] = drawings
                except Exception as e:
                    result.warnings.append(f"Could not parse sheet rels {name}: {e}")

        # Step 4: Parse drawing XML files (DrawingML + VML)
        drawing_anchors: Dict[str, List[Dict]] = {}

        # 4a: Standard DrawingML XML files (xl/drawings/drawing*.xml)
        for name in all_names:
            if re.match(r"xl/drawings/drawing\d+\.xml$", name):
                try:
                    drawing_xml = zf.read(name)
                    drawing_root = _parse_xml_safe(drawing_xml)
                    if drawing_root is None:
                        continue
                    anchors = []
                    for anchor_tag in ["xdr:twoCellAnchor", "xdr:oneCellAnchor", "xdr:absoluteAnchor"]:
                        for anchor in drawing_root.findall(f".//{anchor_tag}", NS):
                            row_0based = _extract_row_from_anchor(anchor)
                            col = _extract_col_from_anchor(anchor)
                            pic = anchor.find(".//xdr:pic", NS)
                            graphicFrame = anchor.find(".//xdr:graphicFrame", NS)
                            rid = None
                            item_type = "image"

                            if pic is not None:
                                blipFill = pic.find(".//a:blipFill", NS)
                                if blipFill is not None:
                                    blip = blipFill.find("a:blip", NS)
                                    if blip is not None:
                                        rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                            elif graphicFrame is not None:
                                graphic = graphicFrame.find(".//a:graphic", NS)
                                if graphic is not None:
                                    graphicData = graphic.find("a:graphicData", NS)
                                    if graphicData is not None:
                                        uri = graphicData.get("uri", "")
                                        if "oleObject" in uri or "chart" in uri:
                                            item_type = "ole"
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

        # 4b: VML Drawing XML files (xl/drawings/vmlDrawing*.vml)
        for name in all_names:
            if re.match(r"xl/drawings/vmlDrawing\d+\.vml$", name):
                try:
                    vml_content = zf.read(name).decode('utf-8', errors='replace')
                    anchors = []
                    # Extract shapes containing imagedata or OLE references
                    shapes = re.findall(r'<v:shape[^>]*>(.*?)</v:shape>', vml_content, re.DOTALL)
                    for shape in shapes:
                        relid_match = re.search(r'(?:o:relid|r:id)=["\']([^"\']+)["\']', shape)
                        anchor_match = re.search(r'<x:Anchor>\s*([^<]+)\s*</x:Anchor>', shape)
                        if relid_match and anchor_match:
                            rid = relid_match.group(1)
                            anchor_text = anchor_match.group(1).strip()
                            nums = [int(n) for n in re.split(r'[,\s]+', anchor_text) if n.strip().isdigit()]
                            if len(nums) >= 4:
                                from_col = nums[0]
                                from_row = nums[2]
                                anchors.append({
                                    "row_0based": from_row,
                                    "col": from_col,
                                    "rId": rid,
                                    "type": "image"
                                })
                    drawing_anchors[name] = anchors
                except Exception as e:
                    result.warnings.append(f"Could not parse VML drawing {name}: {e}")

        # Step 5: Build final row mapping
        asset_counter = 0
        processed_anchors = set()

        for sheet_xml, drawing_list in sheet_to_drawings.items():
            for drawing_xml_name in drawing_list:
                rid_to_media = drawing_rel_map.get(drawing_xml_name, {})
                anchors = drawing_anchors.get(drawing_xml_name, [])

                for anchor in anchors:
                    rid = anchor["rId"]
                    row_0based = anchor["row_0based"]
                    col = anchor["col"]
                    item_type = anchor["type"]
                    excel_row = row_0based + 1  # 1-indexed Excel row

                    field_name = _field_from_col(col, col_field_map)
                    media_fname = rid_to_media.get(rid, "")

                    if not media_fname:
                        continue

                    # Avoid duplicate processing of exact same anchor/media combination
                    dedup_key = (excel_row, field_name, media_fname)
                    if dedup_key in processed_anchors:
                        continue
                    processed_anchors.add(dedup_key)

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
                        continue

                    result.total_images += 1
                    if excel_row not in result.row_assets:
                        result.row_assets[excel_row] = {}
                    if field_name not in result.row_assets[excel_row]:
                        result.row_assets[excel_row][field_name] = []
                    result.row_assets[excel_row][field_name].append(info)

        # Step 6: Fallback if no anchors found
        if not processed_anchors and media_bytes:
            _fallback_scan_worksheet_xml(zf, all_names, media_bytes, ole_bytes, result, col_field_map, max_bytes)

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
    if media_bytes and not result.row_assets:
        result.warnings.append(
            "Could not resolve drawing anchors — images assigned using sequential fallback."
        )
        asset_counter = 0
        for fname, (orig_fname, ext, raw) in media_bytes.items():
            asset_counter += 1
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
