import os
import io
import re
import struct
import xml.etree.ElementTree as ET
from typing import Optional
from PIL import Image

def extract_embedded_raster_image(data: bytes) -> Optional[Image.Image]:
    """
    Scans binary EMF/WMF data for embedded PNG or JPEG magic signatures.
    Many Office / Word EMF/WMF files wrap raw PNG/JPEG images inside record headers.
    Extracting raw PNG/JPEG gives 100% loss-free image recovery.
    """
    if not data:
        return None

    # 1. Search for PNG magic header: \x89PNG\r\n\x1a\n
    png_idx = data.find(b"\x89PNG\r\n\x1a\n")
    if png_idx != -1:
        # Find IEND chunk marker \x00\x00\x00\x00IEND\xaeB`\x82
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
    # Scan for BITMAPINFOHEADER (biSize == 40)
    for i in range(0, min(len(data) - 40, 2048), 2):
        if data[i:i+4] == b"\x28\x00\x00\x00": # biSize = 40
            try:
                w, h, planes, bpp, compression, img_size = struct.unpack("<iiHHII", data[i+4:i+24])
                if 1 <= abs(w) <= 8000 and 1 <= abs(h) <= 8000 and bpp in (1, 4, 8, 16, 24, 32):
                    # Construct valid BMP header (14 bytes) + DIB payload
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

            return Image.frombytes('RGBA', (target_w, target_h), raw_bytes, 'raw', 'BGRA')
        finally:
            gdi32.DeleteEnhMetaFile(hemf)
    except Exception:
        return None


def render_emf_wmf_wand(data: bytes) -> Optional[Image.Image]:
    """Fallback rendering using ImageMagick / Wand if available."""
    try:
        from wand.image import Image as WandImage
        with WandImage(blob=data) as w_img:
            w_img.format = 'png'
            png_bytes = w_img.make_blob()
            img = Image.open(io.BytesIO(png_bytes))
            img.load()
            return img
    except Exception:
        return None


def convert_vector_metafile_to_png_bytes(data: bytes) -> Optional[bytes]:
    """
    Main multi-stage converter for .emf, .wmf, .vml files.
    Returns PNG image bytes or None if conversion fails.
    """
    if not data:
        return None

    # Stage 1: Try PIL Image.open (if format is natively recognized)
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

    # Stage 2: Extract embedded PNG/JPEG/DIB bitmap from EMF/WMF record streams
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

    # Stage 3: Windows GDI32 API Renderer (Windows environment)
    try:
        gdi_img = render_emf_wmf_gdi(data)
        if gdi_img:
            buf = io.BytesIO()
            gdi_img.save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    # Stage 4: Wand / ImageMagick Fallback (Linux Docker environment)
    try:
        wand_img = render_emf_wmf_wand(data)
        if wand_img:
            buf = io.BytesIO()
            wand_img.save(buf, "PNG")
            return buf.getvalue()
    except Exception:
        pass

    return None
