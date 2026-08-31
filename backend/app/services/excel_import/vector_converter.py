import os
import io
import re
import math
import struct
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional
from PIL import Image, ImageDraw, ImageOps

def extract_embedded_raster_image(data: bytes) -> Optional[Image.Image]:
    """
    Scans binary EMF/WMF data for embedded PNG, JPEG, or DIB bitmap magic signatures.
    Extracting raw PNG/JPEG gives 100% loss-free image recovery.
    """
    if not data:
        return None

    # 1. Search for PNG magic header: \x89PNG\r\n\x1a\n
    png_idx = data.find(b"\x89PNG\r\n\x1a\n")
    if png_idx != -1:
        iend_idx = data.find(b"IEND\xaeB`\x82", png_idx)
        if iend_idx != -1:
            png_bytes = data[png_idx : iend_idx + 8]
            try:
                img = Image.open(io.BytesIO(png_bytes))
                img.load()
                return img
            except Exception:
                pass
        else:
            try:
                img = Image.open(io.BytesIO(data[png_idx:]))
                img.load()
                return img
            except Exception:
                pass

    # 2. Search for JPEG magic header: \xff\xd8\xff
    jpeg_idx = data.find(b"\xff\xd8\xff")
    if jpeg_idx != -1:
        jpeg_end = data.find(b"\xff\xd9", jpeg_idx)
        if jpeg_end != -1:
            jpeg_bytes = data[jpeg_idx : jpeg_end + 2]
            try:
                img = Image.open(io.BytesIO(jpeg_bytes))
                img.load()
                return img
            except Exception:
                pass
        else:
            try:
                img = Image.open(io.BytesIO(data[jpeg_idx:]))
                img.load()
                return img
            except Exception:
                pass

    # 3. DIB (Device Independent Bitmap) Header Extraction
    for i in range(0, min(len(data) - 40, 2048), 2):
        if data[i:i+4] == b"\x28\x00\x00\x00": # biSize = 40
            try:
                w, h, planes, bpp, compression, img_size = struct.unpack("<iiHHII", data[i+4:i+24])
                if 1 <= abs(w) <= 8000 and 1 <= abs(h) <= 8000 and bpp in (1, 4, 8, 16, 24, 32):
                    calc_size = img_size if img_size > 0 else abs(w * h * (bpp // 8))
                    off_bits = 14 + 40 + (256 * 4 if bpp <= 8 else 0)
                    file_size = off_bits + calc_size
                    bmp_header = struct.pack("<2sIHHI", b"BM", min(file_size, len(data) - i + 14), 0, 0, off_bits)
                    bmp_data = bmp_header + data[i:i + file_size]
                    img = Image.open(io.BytesIO(bmp_data))
                    img.load()
                    return img
            except Exception:
                continue

    return None


def crop_image_whitespace(img: Image.Image, margin: int = 15) -> Image.Image:
    """Crops excess white background margins to tightly frame vector graphics and chemical equations."""
    try:
        if img.mode in ('RGBA', 'LA'):
            alpha = img.split()[-1]
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=alpha)
        else:
            rgb_img = img.convert('RGB')

        inverted = ImageOps.invert(rgb_img)
        bbox = inverted.getbbox()
        if bbox:
            left = max(bbox[0] - margin, 0)
            top = max(bbox[1] - margin, 0)
            right = min(bbox[2] + margin, img.width)
            bottom = min(bbox[3] + margin, img.height)
            return img.crop((left, top, right, bottom))
    except Exception:
        pass
    return img


def render_emf_pure_python(data: bytes) -> Optional[Image.Image]:
    """
    Universal Pure Python EMF vector drawing interpreter.
    Filters out frame-boundary lines, computes dynamic bounding box of chemical bonds and text labels,
    and renders crisp black vector drawings and text characters on a clean white canvas.
    """
    if not data or len(data) < 80:
        return None
    try:
        itype, nsize = struct.unpack('<II', data[0:8])
        if itype != 1 or data[40:44] != b' EMF':
            return None

        # 1. Parse all vector lines, polygon shapes, and text items
        off = 0
        curr_pt = None
        raw_lines = []
        polygons = []
        text_items = []

        while off < len(data) - 8:
            itype, nsize = struct.unpack('<II', data[off:off+8])
            if nsize <= 0 or off + nsize > len(data): break
            rec = data[off:off+nsize]

            if itype == 27 and len(rec) >= 16: # MOVETOEX
                px, py = struct.unpack('<ii', rec[8:16])
                curr_pt = (px, py)

            elif itype == 54 and len(rec) >= 16: # LINETO
                px, py = struct.unpack('<ii', rec[8:16])
                next_pt = (px, py)
                if curr_pt is not None:
                    dist = math.hypot(next_pt[0] - curr_pt[0], next_pt[1] - curr_pt[1])
                    raw_lines.append((curr_pt, next_pt, dist))
                curr_pt = next_pt

            elif itype == 82 and len(rec) >= 28: # POLYDRAW16
                cpt = struct.unpack('<I', rec[8:12])[0]
                pts = []
                pts_start = 28
                for i in range(cpt):
                    if pts_start + (i+1)*4 <= len(rec):
                        px, py = struct.unpack('<hh', rec[pts_start + i*4 : pts_start + (i+1)*4])
                        pts.append((px, py))
                ab_start = pts_start + cpt * 4
                abTypes = rec[ab_start : ab_start + cpt]
                for i in range(min(cpt, len(abTypes), len(pts))):
                    typ = abTypes[i] & 0x06
                    if typ == 0x06:
                        curr_pt = pts[i]
                    elif typ in (0x02, 0x04):
                        if curr_pt is not None:
                            dist = math.hypot(pts[i][0] - curr_pt[0], pts[i][1] - curr_pt[1])
                            raw_lines.append((curr_pt, pts[i], dist))
                        curr_pt = pts[i]

            elif itype == 74 and len(rec) >= 28: # POLYGON16
                cpt = struct.unpack('<I', rec[8:12])[0]
                pts = []
                pts_start = 28
                for i in range(cpt):
                    if pts_start + (i+1)*4 <= len(rec):
                        px, py = struct.unpack('<hh', rec[pts_start + i*4 : pts_start + (i+1)*4])
                        pts.append((px, py))
                if len(pts) >= 2:
                    polygons.append(pts)

            elif itype == 75 and len(rec) >= 32: # POLYPOLYGON16
                cPolys = struct.unpack('<I', rec[24:28])[0]
                counts_offset = 32
                pts_offset = 32 + cPolys * 4
                curr_p = 0
                for c_idx in range(cPolys):
                    if counts_offset + (c_idx+1)*4 <= len(rec):
                        cnt = struct.unpack('<I', rec[counts_offset + c_idx*4 : counts_offset + (c_idx+1)*4])[0]
                        sub_pts = []
                        for p_idx in range(cnt):
                            idx = curr_p + p_idx
                            if pts_offset + (idx+1)*4 <= len(rec):
                                px, py = struct.unpack('<hh', rec[pts_offset + idx*4 : pts_offset + (idx+1)*4])
                                sub_pts.append((px, py))
                        if len(sub_pts) >= 2:
                            polygons.append(sub_pts)
                        curr_p += cnt

            elif itype in (83, 84) and len(rec) >= 52: # EMR_EXTTEXTOUTA, EMR_EXTTEXTOUTW
                ref_x, ref_y, n_chars, off_str = struct.unpack('<iiII', rec[36:52])
                if off_str + (n_chars * 2 if itype == 84 else n_chars) <= len(rec):
                    raw_bytes = rec[off_str : off_str + (n_chars * 2 if itype == 84 else n_chars)]
                    txt = raw_bytes.decode('utf-16le' if itype == 84 else 'latin-1', errors='ignore')
                    if txt.strip():
                        text_items.append((ref_x, ref_y, txt.strip()))

            off += nsize

        # 2. Filter out abnormal long frame-connecting lines
        dists = sorted([d for _, _, d in raw_lines if d > 5])
        median_d = dists[len(dists)//2] if dists else 200
        max_allowed_dist = max(median_d * 3.5, 800)

        valid_lines = [l_item for l_item in raw_lines if l_item[2] <= max_allowed_dist and l_item[0][1] > 20 and l_item[1][1] > 20]

        valid_pts = []
        for p1, p2, _ in valid_lines:
            valid_pts.extend([p1, p2])
        for poly in polygons:
            valid_pts.extend(poly)
        for rx, ry, _ in text_items:
            valid_pts.append((rx, ry))

        if not valid_pts:
            return None

        min_x, max_x = min(p[0] for p in valid_pts), max(p[0] for p in valid_pts)
        min_y, max_y = min(p[1] for p in valid_pts), max(p[1] for p in valid_pts)
        dw, dh = max(max_x - min_x, 1), max(max_y - min_y, 1)

        target_w = 300
        target_h = max(int(target_w * (dh / dw)), 60)
        img = Image.new('RGBA', (target_w, target_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        margin = 15
        scale_x = (target_w - 2 * margin) / dw
        scale_y = (target_h - 2 * margin) / dh

        for p1, p2, _ in valid_lines:
            sp = (margin + (p1[0] - min_x) * scale_x, margin + (p1[1] - min_y) * scale_y)
            ep = (margin + (p2[0] - min_x) * scale_x, margin + (p2[1] - min_y) * scale_y)
            draw.line([sp, ep], fill=(0, 0, 0, 255), width=3)

        for poly in polygons:
            pts = [(margin + (p[0] - min_x) * scale_x, margin + (p[1] - min_y) * scale_y) for p in poly]
            draw.polygon(pts, outline=(0, 0, 0, 255))

        for rx, ry, txt in text_items:
            tp = (margin + (rx - min_x) * scale_x, margin + (ry - min_y) * scale_y)
            draw.text(tp, txt, fill=(0, 0, 0, 255))

        return crop_image_whitespace(img)
    except Exception:
        return None


def render_wmf_pure_python(data: bytes) -> Optional[Image.Image]:
    """
    Universal Pure Python WMF vector drawing interpreter.
    Filters out frame-boundary lines, computes dynamic bounding box of chemical bonds,
    and renders crisp black vector drawings on a clean white canvas.
    """
    if not data or len(data) < 18:
        return None
    try:
        off = 22 if struct.unpack('<I', data[:4])[0] == 0x9ac6cdd7 else 18
        curr_pt = None
        raw_lines = []
        polygons = []

        scan_off = off
        while scan_off < len(data) - 6:
            rd_size, rd_fn = struct.unpack('<IH', data[scan_off:scan_off+6])
            if rd_size < 3 or scan_off + rd_size*2 > len(data): break
            rec = data[scan_off:scan_off + rd_size*2]

            if rd_fn == 0x0214 and len(rec) >= 10: # MOVETO
                py, px = struct.unpack('<hh', rec[6:10])
                curr_pt = (px, py)

            elif rd_fn == 0x0213 and len(rec) >= 10: # LINETO
                py, px = struct.unpack('<hh', rec[6:10])
                next_pt = (px, py)
                if curr_pt is not None:
                    dist = math.hypot(next_pt[0] - curr_pt[0], next_pt[1] - curr_pt[1])
                    raw_lines.append((curr_pt, next_pt, dist))
                curr_pt = next_pt

            elif rd_fn == 0x0324 and len(rec) >= 8: # POLYGON
                cpt = struct.unpack('<h', rec[6:8])[0]
                pts = []
                for i in range(cpt):
                    if 8 + (i+1)*4 <= len(rec):
                        py, px = struct.unpack('<hh', rec[8 + i*4 : 8 + (i+1)*4])
                        pts.append((px, py))
                if len(pts) >= 2:
                    polygons.append(pts)

            scan_off += rd_size * 2

        dists = sorted([d for _, _, d in raw_lines if d > 5])
        median_d = dists[len(dists)//2] if dists else 200
        max_allowed_dist = max(median_d * 3.5, 800)

        valid_lines = [l_item for l_item in raw_lines if l_item[2] <= max_allowed_dist and l_item[0][1] > 20 and l_item[1][1] > 20]

        valid_pts = []
        for p1, p2, _ in valid_lines:
            valid_pts.extend([p1, p2])
        for poly in polygons:
            valid_pts.extend(poly)

        if not valid_pts:
            return None

        min_x, max_x = min(p[0] for p in valid_pts), max(p[0] for p in valid_pts)
        min_y, max_y = min(p[1] for p in valid_pts), max(p[1] for p in valid_pts)
        dw, dh = max(max_x - min_x, 1), max(max_y - min_y, 1)

        target_w = 300
        target_h = max(int(target_w * (dh / dw)), 30)
        img = Image.new('RGBA', (target_w, target_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)

        margin = 15
        scale_x = (target_w - 2 * margin) / dw
        scale_y = (target_h - 2 * margin) / dh

        for p1, p2, _ in valid_lines:
            sp = (margin + (p1[0] - min_x) * scale_x, margin + (p1[1] - min_y) * scale_y)
            ep = (margin + (p2[0] - min_x) * scale_x, margin + (p2[1] - min_y) * scale_y)
            draw.line([sp, ep], fill=(0, 0, 0, 255), width=3)

        for poly in polygons:
            pts = [(margin + (p[0] - min_x) * scale_x, margin + (p[1] - min_y) * scale_y) for p in poly]
            draw.polygon(pts, outline=(0, 0, 0, 255))

        return crop_image_whitespace(img)
    except Exception:
        return None


def render_emf_wmf_libreoffice(data: bytes) -> Optional[Image.Image]:
    """Renders EMF/WMF using LibreOffice CLI if installed in environment, cropped tightly."""
    if not data:
        return None
    try:
        import tempfile
        ext = ".emf" if (len(data) >= 44 and data[40:44] == b" EMF") else ".wmf"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_in:
            tmp_in.write(data)
            tmp_in_path = tmp_in.name

        out_dir = os.path.dirname(tmp_in_path)
        cmd = ["soffice", "--headless", "--convert-to", "png", "--outdir", out_dir, tmp_in_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)

        png_path = os.path.splitext(tmp_in_path)[0] + ".png"
        if os.path.exists(png_path):
            img = Image.open(png_path)
            img.load()
            cropped = crop_image_whitespace(img)
            os.remove(png_path)
            if os.path.exists(tmp_in_path):
                os.remove(tmp_in_path)
            return cropped
        if os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
    except Exception:
        pass
    return None


def render_emf_wmf_gdi(data: bytes) -> Optional[Image.Image]:
    """Render Windows EMF/WMF vector metafile bytes into a PIL Image via Windows GDI32."""
    if not data or os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

        class ENHMETAHEADER(ctypes.Structure):
            _fields_ = [
                ('iType', wintypes.DWORD), ('nSize', wintypes.DWORD),
                ('rclBounds', RECT), ('rclFrame', RECT),
                ('dSignature', wintypes.DWORD), ('nVersion', wintypes.DWORD),
                ('nBytes', wintypes.DWORD), ('nRecords', wintypes.DWORD),
                ('nHandles', wintypes.WORD), ('sReserved', wintypes.WORD),
                ('nDescription', wintypes.DWORD), ('offDescription', wintypes.DWORD),
                ('nPalEntries', wintypes.DWORD), ('szlDevice', wintypes.SIZE),
                ('szlMillimeters', wintypes.SIZE)
            ]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long),
                ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]

        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32

        hemf = gdi32.SetEnhMetaFileBits(len(data), (ctypes.c_ubyte * len(data))(*data))
        if not hemf:
            hemf = gdi32.SetWinMetaFileBits(len(data), (ctypes.c_ubyte * len(data))(*data), None, None)
        if not hemf:
            return None

        try:
            header = ENHMETAHEADER()
            if not gdi32.GetEnhMetaFileHeader(hemf, ctypes.sizeof(header), ctypes.byref(header)):
                return None

            w = header.rclBounds.right - header.rclBounds.left
            h = header.rclBounds.bottom - header.rclBounds.top
            if w <= 0 or h <= 0:
                w = header.rclFrame.right - header.rclFrame.left
                h = header.rclFrame.bottom - header.rclFrame.top
            if w <= 0: w = 400
            if h <= 0: h = 300

            target_w = max(w * 2, 400)
            target_h = max(h * 2, 300)

            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = target_w
            bmi.bmiHeader.biHeight = -target_h  # Top-down bitmap
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            p_bits = ctypes.c_void_p()
            hbmp = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(p_bits), None, 0)
            if not hbmp or not p_bits:
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                return None

            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

            white_brush = gdi32.CreateSolidBrush(0x00FFFFFF)
            rect = RECT(0, 0, target_w, target_h)
            user32.FillRect(hdc_mem, ctypes.byref(rect), white_brush)
            gdi32.DeleteObject(white_brush)

            gdi32.PlayEnhMetaFile(hdc_mem, hemf, ctypes.byref(rect))

            buf_size = target_w * target_h * 4
            buffer = (ctypes.c_ubyte * buf_size).from_address(p_bits.value)
            raw_bytes = bytes(buffer)

            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            raw_img = Image.frombytes('RGBA', (target_w, target_h), raw_bytes, 'raw', 'BGRA')
            return crop_image_whitespace(raw_img)
        finally:
            gdi32.DeleteEnhMetaFile(hemf)
    except Exception:
        return None


def convert_vector_metafile_to_png_bytes(data: bytes) -> Optional[bytes]:
    """
    Main multi-stage converter for .emf, .wmf, .vml files.
    Prefers LibreOffice for 100% loss-free vector & text rendering, with Pure Python and GDI fallbacks.
    """
    if not data:
        return None

    # Stage 1: LibreOffice CLI Converter (100% loss-free vector & text rendering)
    try:
        lo_img = render_emf_wmf_libreoffice(data)
        if lo_img:
            buf = io.BytesIO()
            if lo_img.mode in ("RGBA", "LA"):
                lo_img.save(buf, "PNG")
            else:
                lo_img.convert("RGB").save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Stage 2: Extract embedded PNG/JPEG/DIB bitmap
    try:
        extracted = extract_embedded_raster_image(data)
        if extracted:
            buf = io.BytesIO()
            if extracted.mode in ("RGBA", "LA"):
                extracted.save(buf, "PNG")
            else:
                extracted.convert("RGB").save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Stage 3: Try PIL Image.open directly
    try:
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img.convert("RGBA").save(buf, "PNG")
        else:
            img.convert("RGB").save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        pass

    # Stage 4: Universal Pure Python EMF / WMF Vector & Text Renderer
    try:
        emf_img = render_emf_pure_python(data)
        if emf_img:
            buf = io.BytesIO()
            emf_img.save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    try:
        wmf_img = render_wmf_pure_python(data)
        if wmf_img:
            buf = io.BytesIO()
            wmf_img.save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Stage 5: Windows GDI32 API Renderer (Windows environment)
    try:
        gdi_img = render_emf_wmf_gdi(data)
        if gdi_img:
            buf = io.BytesIO()
            gdi_img.save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    return None
