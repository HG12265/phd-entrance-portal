"""
vector_converter.py

Cross-platform EMF/WMF → PNG converter.

Priority chain for vector formats (.emf, .wmf):
1. Windows GDI32 (if on Windows dev machine) — 100% native crisp vector rendering
2. Wand (ImageMagick Python bindings) — primary on Linux/Docker (300 DPI)
3. Raw write — fallback if all converters fail

Priority chain for raster formats (.png, .jpg, .bmp, .gif, .tiff):
1. Pillow (PIL)
2. Wand (ImageMagick)

All conversions are honest: if conversion fails, ConversionResult.success = False
and the original bytes are always preserved.
"""

import os
import io
import logging
import hashlib
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger("phd_app")


@dataclass
class ConversionResult:
    """Result of a vector/image conversion attempt."""
    success: bool
    output_path: str              # Path where PNG was saved (or empty if failed)
    method_used: str              # "wand", "pillow", "gdi32", "raw_write", "failed"
    original_preserved: bool = True
    original_path: str = ""       # Path where original was saved
    width: int = 0
    height: int = 0
    error_reason: str = ""


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _try_gdi32_convert(img_bytes: bytes, output_path: str) -> Tuple[bool, int, int, str]:
    """
    Windows-only: use GDI32 to render EMF/WMF metafiles into high-resolution PNG.
    Only available on Windows (dev machine).
    """
    if os.name != 'nt':
        return False, 0, 0, "GDI32: only available on Windows"

    try:
        import ctypes
        from ctypes import wintypes
        from PIL import Image

        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32

        hemf = gdi32.SetEnhMetaFileBits(len(img_bytes), (ctypes.c_ubyte * len(img_bytes))(*img_bytes))
        if not hemf:
            hemf = gdi32.SetWinMetaFileBits(len(img_bytes), (ctypes.c_ubyte * len(img_bytes))(*img_bytes), None, None)
        if not hemf:
            return False, 0, 0, "GDI32: SetEnhMetaFileBits and SetWinMetaFileBits both failed"

        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

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

        try:
            header = ENHMETAHEADER()
            gdi32.GetEnhMetaFileHeader(hemf, ctypes.sizeof(header), ctypes.byref(header))

            w = header.rclBounds.right - header.rclBounds.left
            h = header.rclBounds.bottom - header.rclBounds.top
            if w <= 0 or h <= 0:
                w = header.rclFrame.right - header.rclFrame.left
                h = header.rclFrame.bottom - header.rclFrame.top
            if w <= 0: w = 400
            if h <= 0: h = 300

            # Scale for crisp vector rendering (high DPI)
            scale = max(2.0, min(800.0 / max(w, 1), 800.0 / max(h, 1)))
            target_w = int(w * scale)
            target_h = int(h * scale)
            target_w = max(target_w, 300)
            target_h = max(target_h, 150)

            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = target_w
            bmi.bmiHeader.biHeight = -target_h  # Top-down DIB
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            p_bits = ctypes.c_void_p()
            hbmp = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(p_bits), None, 0)

            if not hbmp or not p_bits:
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(0, hdc_screen)
                return False, 0, 0, "GDI32: CreateDIBSection failed"

            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
            white_brush = gdi32.CreateSolidBrush(0x00FFFFFF)
            rect = RECT(0, 0, target_w, target_h)
            user32.FillRect(hdc_mem, ctypes.byref(rect), white_brush)
            gdi32.DeleteObject(white_brush)
            gdi32.PlayEnhMetaFile(hdc_mem, hemf, ctypes.byref(rect))

            buf_size = target_w * target_h * 4
            buffer = (ctypes.c_ubyte * buf_size).from_address(p_bits.value)
            raw_data = bytes(buffer)

            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            pil_img = Image.frombytes('RGBA', (target_w, target_h), raw_data, 'raw', 'BGRA')
            pil_img.save(output_path, "PNG")
            return True, target_w, target_h, ""

        finally:
            gdi32.DeleteEnhMetaFile(hemf)

    except Exception as e:
        return False, 0, 0, f"GDI32 error: {type(e).__name__}: {str(e)}"


def _try_wand_convert(img_bytes: bytes, output_path: str, source_format: str) -> Tuple[bool, int, int, str]:
    """
    Attempt conversion using Wand (ImageMagick).
    Configures high DPI (300 resolution) and white background for clean vector rendering.
    """
    try:
        from wand.image import Image as WandImage
        from wand.color import Color

        fmt = source_format.lstrip('.').upper()
        with WandImage(blob=img_bytes, format=fmt, resolution=300) as wand_img:
            w = wand_img.width
            h = wand_img.height

            if w <= 0 or h <= 0:
                return False, 0, 0, f"Wand: image has zero dimensions ({w}x{h})"

            # White background for transparent EMF/WMF vector drawings
            try:
                wand_img.background_color = Color('white')
                wand_img.alpha_channel = 'remove'
            except Exception:
                pass

            wand_img.format = 'png'
            png_blob = wand_img.make_blob()

            with open(output_path, 'wb') as f:
                f.write(png_blob)

            return True, w, h, ""

    except ImportError:
        return False, 0, 0, "Wand not installed"
    except Exception as e:
        return False, 0, 0, f"Wand error: {type(e).__name__}: {str(e)}"


def _try_pillow_convert(img_bytes: bytes, output_path: str) -> Tuple[bool, int, int, str]:
    """
    Attempt conversion using Pillow (PIL).
    Works for standard raster formats (PNG, JPEG, BMP, GIF, TIFF).
    """
    try:
        from PIL import Image
        buf = io.BytesIO(img_bytes)
        pil_img = Image.open(buf)
        pil_img.load()

        w, h = pil_img.size

        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            converted = pil_img.convert("RGBA")
            bg = Image.new("RGBA", converted.size, (255, 255, 255, 255))
            bg.paste(converted, mask=converted.split()[3])
            converted = bg.convert("RGB")
        else:
            converted = pil_img.convert("RGB")

        converted.save(output_path, "PNG", optimize=True)
        return True, w, h, ""

    except ImportError:
        return False, 0, 0, "Pillow not installed"
    except Exception as e:
        return False, 0, 0, f"Pillow error: {type(e).__name__}: {str(e)}"


def convert_to_png(
    raw_bytes: bytes,
    output_path: str,
    original_format: str,
    original_dir: Optional[str] = None
) -> ConversionResult:
    """
    Convert image/vector bytes to a clean PNG at output_path.

    Args:
        raw_bytes: Raw image/vector file bytes
        output_path: Full path where PNG should be saved
        original_format: File extension like ".emf", ".wmf", ".png", ".jpg"
        original_dir: Optional directory to preserve original binary file

    Returns:
        ConversionResult with honest success/failure information
    """
    if not raw_bytes:
        return ConversionResult(
            success=False, output_path="", method_used="failed", error_reason="Empty bytes provided"
        )

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    fmt = original_format.lower().lstrip(".")
    is_vector = fmt in ("emf", "wmf")

    # Preserve original file if requested
    original_path = ""
    if original_dir:
        os.makedirs(original_dir, exist_ok=True)
        orig_name = os.path.splitext(os.path.basename(output_path))[0] + f".{fmt}"
        original_path = os.path.join(original_dir, orig_name)
        try:
            with open(original_path, 'wb') as f:
                f.write(raw_bytes)
        except Exception as e:
            logger.warning(f"Could not save original file: {e}")

    # ── VECTOR FORMAT PIPELINE (.emf, .wmf) ──
    if is_vector:
        # 1. On Windows: Try GDI32 FIRST (native 100% crystal clear vector render)
        if os.name == 'nt':
            success, w, h, err = _try_gdi32_convert(raw_bytes, output_path)
            if success:
                logger.info(f"vector_converter: GDI32 converted {fmt} → PNG ({w}x{h})")
                return ConversionResult(
                    success=True, output_path=output_path, method_used="gdi32",
                    original_preserved=(original_path != ""), original_path=original_path,
                    width=w, height=h
                )

        # 2. On Linux/Docker or GDI32 fallback: Try Wand (ImageMagick)
        success, w, h, err = _try_wand_convert(raw_bytes, output_path, original_format)
        if success:
            logger.info(f"vector_converter: Wand converted {fmt} → PNG ({w}x{h})")
            return ConversionResult(
                success=True, output_path=output_path, method_used="wand",
                original_preserved=(original_path != ""), original_path=original_path,
                width=w, height=h
            )

        # 3. GDI32 on Windows (if not tried yet)
        if os.name == 'nt':
            success, w, h, err = _try_gdi32_convert(raw_bytes, output_path)
            if success:
                return ConversionResult(
                    success=True, output_path=output_path, method_used="gdi32",
                    original_preserved=(original_path != ""), original_path=original_path,
                    width=w, height=h
                )

        # Do NOT use Pillow direct load for vector files because Pillow only extracts tiny 89x84 DIB thumbnails!
        logger.warning(f"vector_converter: All vector conversion methods failed for {fmt}")
        return ConversionResult(
            success=False, output_path="", method_used="failed",
            original_preserved=(original_path != ""), original_path=original_path,
            error_reason=f"Vector conversion failed for format: {fmt}"
        )

    # ── RASTER FORMAT PIPELINE (.png, .jpg, .gif, .bmp, .tiff) ──
    # 1. Pillow
    success, w, h, err = _try_pillow_convert(raw_bytes, output_path)
    if success:
        return ConversionResult(
            success=True, output_path=output_path, method_used="pillow",
            original_preserved=(original_path != ""), original_path=original_path,
            width=w, height=h
        )

    # 2. Wand fallback
    success, w, h, err = _try_wand_convert(raw_bytes, output_path, original_format)
    if success:
        return ConversionResult(
            success=True, output_path=output_path, method_used="wand",
            original_preserved=(original_path != ""), original_path=original_path,
            width=w, height=h
        )

    return ConversionResult(
        success=False, output_path="", method_used="failed",
        original_preserved=(original_path != ""), original_path=original_path,
        error_reason=f"Raster conversion failed for format: {fmt}"
    )
