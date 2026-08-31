import os
import io
import zipfile
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from app.services.excel_import.vector_converter import convert_vector_metafile_to_png_bytes

def extract_all_xlsx_media_images(xlsx_filepath: str, output_dir: str, batch_id: str) -> Dict[str, str]:
    """
    Scans the zip container of an .xlsx file and extracts all media files
    from xl/media/ (including .emf, .wmf, .vml, .png, .jpeg, .svg).
    Converts vector metafiles (.emf, .wmf, .vml) to standard PNG format.
    Returns a dictionary mapping media_filename -> relative_web_url.
    """
    extracted_map = {}
    if not os.path.exists(xlsx_filepath) or not zipfile.is_zipfile(xlsx_filepath):
        return extracted_map

    os.makedirs(output_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(xlsx_filepath, 'r') as z:
            media_files = [f for f in z.namelist() if f.startswith('xl/media/')]
            
            for media_path in media_files:
                filename = os.path.basename(media_path)
                ext = os.path.splitext(filename)[1].lower()
                raw_bytes = z.read(media_path)

                if not raw_bytes:
                    continue

                if ext in ['.emf', '.wmf', '.vml']:
                    png_bytes = convert_vector_metafile_to_png_bytes(raw_bytes)
                    if png_bytes:
                        out_filename = f"q_img_{batch_id}_{os.path.splitext(filename)[0]}.png"
                        out_filepath = os.path.join(output_dir, out_filename)
                        with open(out_filepath, "wb") as f_out:
                            f_out.write(png_bytes)
                        extracted_map[filename] = f"/static/question_images/{out_filename}"
                else:
                    clean_ext = ext if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'] else '.png'
                    out_filename = f"q_img_{batch_id}_{os.path.splitext(filename)[0]}{clean_ext}"
                    out_filepath = os.path.join(output_dir, out_filename)
                    with open(out_filepath, "wb") as f_out:
                        f_out.write(raw_bytes)
                    extracted_map[filename] = f"/static/question_images/{out_filename}"
    except Exception as e:
        print(f"Error inspecting xlsx media images: {e}")

    return extracted_map


def extract_excel_drawings_with_anchors(
    xlsx_filepath: str,
    output_dir: str,
    batch_id: str,
    col_field_map: Dict[int, str]
) -> Dict[int, Dict[str, List[str]]]:
    """
    Parses OpenXML xl/drawings/drawing*.xml and xl/drawings/_rels/drawing*.xml.rels directly from the .xlsx zip archive.
    Extracts 100% of images (EMF, WMF, VML, PNG, JPG, SVG), converts vector images to PNG,
    and maps them to exact Excel row number (1-indexed) and field name (question_text, option_a, etc.).
    """
    row_field_images = {}
    if not os.path.exists(xlsx_filepath) or not zipfile.is_zipfile(xlsx_filepath):
        return row_field_images

    os.makedirs(output_dir, exist_ok=True)

    namespaces = {
        'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing',
        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
        'v': 'urn:schemas-microsoft-com:vml',
        'o': 'urn:schemas-microsoft-com:office:office'
    }

    try:
        with zipfile.ZipFile(xlsx_filepath, 'r') as z:
            namelist = z.namelist()
            
            drawing_files = [f for f in namelist if f.startswith('xl/drawings/drawing') and f.endswith('.xml')]
            
            for d_file in drawing_files:
                rels_file = f"xl/drawings/_rels/{os.path.basename(d_file)}.rels"
                rel_map = {}
                if rels_file in namelist:
                    try:
                        rel_tree = ET.fromstring(z.read(rels_file))
                        for r_node in rel_tree:
                            r_id = r_node.attrib.get('Id')
                            target = r_node.attrib.get('Target')
                            if r_id and target:
                                rel_map[r_id] = target
                    except Exception:
                        pass

                try:
                    d_tree = ET.fromstring(z.read(d_file))
                    for anchor in d_tree:
                        tag = anchor.tag.split('}')[-1]
                        if tag not in ('twoCellAnchor', 'oneCellAnchor'):
                            continue

                        from_node = anchor.find('xdr:from', namespaces)
                        if from_node is None:
                            continue

                        col_el = from_node.find('xdr:col', namespaces)
                        row_el = from_node.find('xdr:row', namespaces)

                        if col_el is None or row_el is None:
                            continue

                        try:
                            col_num = int(col_el.text)
                            row_num = int(row_el.text) + 1  # 0-indexed row to 1-indexed Excel row!
                        except (ValueError, TypeError):
                            continue

                        blip_nodes = anchor.findall('.//a:blip', namespaces)
                        for blip in blip_nodes:
                            embed_id = blip.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                            if not embed_id or embed_id not in rel_map:
                                continue

                            target_media = rel_map[embed_id]
                            if target_media.startswith('../'):
                                target_media = f"xl/{target_media[3:]}"
                            elif not target_media.startswith('xl/'):
                                target_media = f"xl/media/{os.path.basename(target_media)}"

                            if target_media not in namelist:
                                continue

                            media_bytes = z.read(target_media)
                            if not media_bytes:
                                continue

                            ext = os.path.splitext(target_media)[1].lower()
                            field_name = col_field_map.get(col_num, "question_text")
                            if field_name not in ["question_text", "option_a", "option_b", "option_c", "option_d"]:
                                field_name = "question_text"

                            img_filename = f"q_img_{batch_id}_r{row_num}_{field_name}_{uuid.uuid4().hex[:8]}.png"
                            img_path = os.path.join(output_dir, img_filename)

                            converted_ok = False
                            if ext in ['.emf', '.wmf', '.vml']:
                                png_bytes = convert_vector_metafile_to_png_bytes(media_bytes)
                                if png_bytes:
                                    with open(img_path, "wb") as f_out:
                                        f_out.write(png_bytes)
                                    converted_ok = True
                            else:
                                from app.utils.image_converter import convert_image_bytes_to_png
                                converted_ok = convert_image_bytes_to_png(media_bytes, img_path)

                            if converted_ok:
                                web_url = f"/static/question_images/{img_filename}"
                                if row_num not in row_field_images:
                                    row_field_images[row_num] = {}
                                if field_name not in row_field_images[row_num]:
                                    row_field_images[row_num][field_name] = []
                                row_field_images[row_num][field_name].append(web_url)
                except Exception as d_err:
                    print(f"Error reading drawing XML {d_file}: {d_err}")

    except Exception as e:
        print(f"Error parsing xlsx drawings: {e}")

    return row_field_images
