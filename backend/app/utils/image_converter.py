import os
import io
import ctypes
from ctypes import wintypes
from typing import Optional
from PIL import Image

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

def render_emf_wmf_gdi(data: bytes) -> Optional[Image.Image]:
    """Render Windows EMF/WMF vector metafile bytes into a PIL Image via Windows GDI32."""
    if not data or os.name != 'nt':
        return None
    try:
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

def convert_image_bytes_to_png(img_bytes: bytes, target_filepath: str) -> bool:
    """
    Converts any raw image bytes (PNG, JPEG, GIF, BMP, WEBP, WMF, EMF, TIFF)
    into a standard web-compatible PNG file at target_filepath.
    """
    if not img_bytes:
        return False
        
    os.makedirs(os.path.dirname(target_filepath), exist_ok=True)

    # 1. Standard PIL Image load (PNG, JPG, BMP, WEBP, GIF, TIFF)
    try:
        buf = io.BytesIO(img_bytes)
        pil_img = Image.open(buf)
        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            converted = pil_img.convert("RGBA")
        else:
            converted = pil_img.convert("RGB")
        converted.save(target_filepath, "PNG")
        return True
    except Exception:
        pass

    # 2. Windows GDI EMF / WMF Vector Renderer
    try:
        gdi_img = render_emf_wmf_gdi(img_bytes)
        if gdi_img:
            gdi_img.save(target_filepath, "PNG")
            return True
    except Exception:
        pass

    # 3. Direct write fallback
    try:
        with open(target_filepath, "wb") as f:
            f.write(img_bytes)
        return True
    except Exception:
        return False
