"""
vector_converter.py

Cross-platform EMF/WMF → PNG converter.

Priority chain:
1. Wand (ImageMagick Python bindings) — primary, works on Linux/Docker
2. Pillow direct load — works for some raster formats embedded in EMF headers
3. Windows GDI32 (ctypes) — only on Windows (dev machine), not in Docker
4. Raw bytes write — last resort, marks asset as unconverted

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


def _try_wand_convert(img_bytes: bytes, output_path: str, source_format: str) -> Tuple[bool, int, int, str]:
    """
    Attempt conversion using Wand (ImageMagick).
    Returns (success, width, height, error_msg).
    """
    try:
        from wand.image import Image as WandImage
        from wand.exceptions import WandException

        with WandImage(blob=img_bytes, format=source_format.lstrip('.').upper()) as wand_img:
            # Ensure good resolution for equations/diagrams
            if wand_img.resolution[0] < 150:
                wand_img.resolution = (200, 200)

            w = wand_img.width
            h = wand_img.height

            # Reasonable size check
            if w <= 0 or h <= 0:
                return False, 0, 0, f"Wand: image has zero dimensions ({w}x{h})"

            # Convert to PNG with white background (for transparency)
            wand_img.background_color = wand_img.background_color.__class__('white')
            wand_img.alpha_channel = 'remove'
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
    Works for PNG, JPEG, BMP, GIF, TIFF and some special formats.
    """
    try:
        from PIL import Image
        buf = io.BytesIO(img_bytes)
        pil_img = Image.open(buf)
        pil_img.load()  # Force load to catch format errors

        w, h = pil_img.size

        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            converted = pil_img.convert("RGBA")
            # Composite on white background
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


def _try_gdi32_convert(img_bytes: bytes, output_path: str) -> Tuple[bool, int, int, str]:
    """
    Windows-only: use GDI32 to render EMF/WMF metafiles.
    Only available on Windows (dev machine), not in Docker/Linux.
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

            w = max(header.rclBounds.right - header.rclBounds.left, 100)
            h = max(header.rclBounds.bottom - header.rclBounds.top, 100)
            target_w = max(w * 2, 400)
            target_h = max(h * 2, 300)

            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = target_w
            bmi.bmiHeader.biHeight = -target_h
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


def convert_to_png(
    raw_bytes: bytes,
    output_path: str,
    original_format: str,
    original_dir: Optional[str] = None
) -> ConversionResult:
    """
    Convert image bytes (any format) to PNG at output_path.

    Tries in priority order:
    1. Wand (ImageMagick) — primary for EMF/WMF on Linux/Docker
    2. Pillow — for standard raster formats
    3. Windows GDI32 — only on Windows dev machine
    4. Raw write — last resort

    Args:
        raw_bytes: Raw image/vector file bytes
        output_path: Full path where PNG should be saved
        original_format: File extension like ".emf", ".wmf", ".png", ".jpg"
        original_dir: If provided, saves original bytes here too

    Returns:
        ConversionResult with honest success/failure information
    """
    if not raw_bytes:
        return ConversionResult(
            success=False,
            output_path="",
            method_used="failed",
            error_reason="Empty bytes provided"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fmt = original_format.lower().lstrip(".")
    is_vector = fmt in ("emf", "wmf")

    # Save original file if original_dir is provided
    original_path = ""
    if original_dir:
        os.makedirs(original_dir, exist_ok=True)
        orig_name = os.path.splitext(os.path.basename(output_path))[0] + original_format
        original_path = os.path.join(original_dir, orig_name)
        try:
            with open(original_path, 'wb') as f:
                f.write(raw_bytes)
        except Exception as e:
            logger.warning(f"Could not save original file: {e}")

    # --- Try 1: Wand (EMF/WMF primary on Linux) ---
    if is_vector or fmt in ("tiff", "tif", "bmp", "gif"):
        success, w, h, err = _try_wand_convert(raw_bytes, output_path, original_format)
        if success:
            logger.info(f"vector_converter: Wand converted {fmt} → PNG ({w}x{h})")
            return ConversionResult(
                success=True, output_path=output_path,
                method_used="wand", original_preserved=(original_path != ""),
                original_path=original_path, width=w, height=h
            )
        else:
            logger.debug(f"vector_converter: Wand failed for {fmt}: {err}")

    # --- Try 2: Pillow (works for PNG, JPG, BMP, GIF, TIFF, etc.) ---
    success, w, h, err = _try_pillow_convert(raw_bytes, output_path)
    if success:
        logger.info(f"vector_converter: Pillow converted {fmt} → PNG ({w}x{h})")
        return ConversionResult(
            success=True, output_path=output_path,
            method_used="pillow", original_preserved=(original_path != ""),
            original_path=original_path, width=w, height=h
        )
    else:
        logger.debug(f"vector_converter: Pillow failed for {fmt}: {err}")

    # --- Try 3: Wand for non-vector too (retry with explicit format) ---
    if not is_vector:
        success, w, h, err = _try_wand_convert(raw_bytes, output_path, original_format)
        if success:
            logger.info(f"vector_converter: Wand (retry) converted {fmt} → PNG ({w}x{h})")
            return ConversionResult(
                success=True, output_path=output_path,
                method_used="wand", original_preserved=(original_path != ""),
                original_path=original_path, width=w, height=h
            )

    # --- Try 4: Windows GDI32 (dev machine only) ---
    if is_vector:
        success, w, h, err = _try_gdi32_convert(raw_bytes, output_path)
        if success:
            logger.info(f"vector_converter: GDI32 converted {fmt} → PNG ({w}x{h})")
            return ConversionResult(
                success=True, output_path=output_path,
                method_used="gdi32", original_preserved=(original_path != ""),
                original_path=original_path, width=w, height=h
            )
        else:
            logger.debug(f"vector_converter: GDI32 failed for {fmt}: {err}")

    # --- All methods failed ---
    logger.warning(
        f"vector_converter: All conversion methods failed for format={fmt}, "
        f"size={len(raw_bytes)} bytes. Original {'preserved at ' + original_path if original_path else 'NOT preserved'}."
    )

    return ConversionResult(
        success=False,
        output_path="",
        method_used="failed",
        original_preserved=(original_path != ""),
        original_path=original_path,
        error_reason=f"All conversion methods failed for format: {fmt}"
    )


def is_wand_available() -> bool:
    """Check if Wand (ImageMagick) is available."""
    try:
        import wand.image  # noqa
        return True
    except ImportError:
        return False


def is_imagemagick_emf_supported() -> bool:
    """
    Test if ImageMagick can actually convert a minimal EMF file.
    Returns True only if the end-to-end conversion works.
    """
    if not is_wand_available():
        return False

    # Minimal valid EMF header (40-byte header, EMR_HEADER record type=1)
    # This is the smallest valid EMF structure
    minimal_emf = bytes([
        0x01, 0x00, 0x00, 0x00,  # iType = EMR_HEADER (1)
        0x58, 0x00, 0x00, 0x00,  # nSize = 88 bytes
        0x00, 0x00, 0x00, 0x00,  # rclBounds left
        0x00, 0x00, 0x00, 0x00,  # rclBounds top
        0x64, 0x00, 0x00, 0x00,  # rclBounds right = 100
        0x64, 0x00, 0x00, 0x00,  # rclBounds bottom = 100
        0x00, 0x00, 0x00, 0x00,  # rclFrame left
        0x00, 0x00, 0x00, 0x00,  # rclFrame top
        0x27, 0x0B, 0x00, 0x00,  # rclFrame right
        0x27, 0x0B, 0x00, 0x00,  # rclFrame bottom
        0x20, 0x45, 0x4D, 0x46,  # dSignature = " EMF"
        0x00, 0x00, 0x01, 0x00,  # nVersion
        0x58, 0x00, 0x00, 0x00,  # nBytes
        0x02, 0x00, 0x00, 0x00,  # nRecords = 2 (header + EOF)
        0x00, 0x00,              # nHandles
        0x00, 0x00,              # sReserved
        0x00, 0x00, 0x00, 0x00,  # nDescription
        0x00, 0x00, 0x00, 0x00,  # offDescription
        0x00, 0x00, 0x00, 0x00,  # nPalEntries
        0x00, 0x04, 0x00, 0x00,  # szlDevice width
        0x00, 0x03, 0x00, 0x00,  # szlDevice height
        0x00, 0x00, 0x00, 0x00,  # szlMillimeters width
        0x00, 0x00, 0x00, 0x00,  # szlMillimeters height
        # EMR_EOF record
        0x0E, 0x00, 0x00, 0x00,  # iType = EMR_EOF (14)
        0x14, 0x00, 0x00, 0x00,  # nSize = 20
        0x00, 0x00, 0x00, 0x00,  # nPalEntries
        0x10, 0x00, 0x00, 0x00,  # offPalEntries
        0x14, 0x00, 0x00, 0x00,  # nSizeLast
    ])

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".emf", delete=False) as tmp_in:
        tmp_in.write(minimal_emf)
        tmp_path = tmp_in.name

    out_path = tmp_path + ".png"
    try:
        result = convert_to_png(minimal_emf, out_path, ".emf")
        return result.success
    except Exception:
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        try:
            if os.path.exists(out_path):
                os.unlink(out_path)
        except Exception:
            pass
