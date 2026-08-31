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
                    # Convert vector metafile to PNG
                    png_bytes = convert_vector_metafile_to_png_bytes(raw_bytes)
                    if png_bytes:
                        out_filename = f"q_img_{batch_id}_{os.path.splitext(filename)[0]}.png"
                        out_filepath = os.path.join(output_dir, out_filename)
                        with open(out_filepath, "wb") as f_out:
                            f_out.write(png_bytes)
                        extracted_map[filename] = f"/static/question_images/{out_filename}"
                else:
                    # Standard PNG/JPEG/GIF/SVG
                    clean_ext = ext if ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'] else '.png'
                    out_filename = f"q_img_{batch_id}_{os.path.splitext(filename)[0]}{clean_ext}"
                    out_filepath = os.path.join(output_dir, out_filename)
                    with open(out_filepath, "wb") as f_out:
                        f_out.write(raw_bytes)
                    extracted_map[filename] = f"/static/question_images/{out_filename}"
    except Exception as e:
        print(f"Error inspecting xlsx media images: {e}")

    return extracted_map
