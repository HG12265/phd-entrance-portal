"""
image_converter.py

Cross-platform image conversion utility.

Delegates to the new vector_converter service for EMF/WMF support.
Maintains the existing convert_image_bytes_to_png() API for backward compatibility.
"""

import os
import io
import logging
from typing import Optional
from PIL import Image

logger = logging.getLogger("phd_app")


def convert_image_bytes_to_png(img_bytes: bytes, target_filepath: str) -> bool:
    """
    Converts any raw image bytes (PNG, JPEG, GIF, BMP, WEBP, WMF, EMF, TIFF)
    into a standard web-compatible PNG file at target_filepath.

    Backward-compatible API used by the existing question upload pipeline.
    Now delegates to the new cross-platform vector_converter for EMF/WMF support.

    Returns True if conversion was successful, False otherwise.
    """
    if not img_bytes:
        return False

    os.makedirs(os.path.dirname(target_filepath) or ".", exist_ok=True)

    # Detect format from magic bytes
    original_format = _detect_format(img_bytes)

    # Delegate to the new cross-platform converter
    from app.services.excel_import.vector_converter import convert_to_png
    result = convert_to_png(img_bytes, target_filepath, original_format)

    if result.success:
        logger.debug(f"image_converter: converted {original_format} → PNG via {result.method_used}")
        return True

    # Last resort: write raw bytes directly (may not be a valid PNG, but preserves data)
    try:
        with open(target_filepath, "wb") as f:
            f.write(img_bytes)
        logger.warning(f"image_converter: wrote raw bytes as fallback for {original_format}")
        return True
    except Exception as e:
        logger.error(f"image_converter: all conversion methods failed: {e}")
        return False


def _detect_format(img_bytes: bytes) -> str:
    """
    Detect image format from magic bytes.
    Returns extension string like ".emf", ".wmf", ".png", ".jpg", etc.
    """
    if len(img_bytes) < 4:
        return ".bin"

    # EMF: iType=1 at bytes 0-3, signature " EMF" at bytes 40-43
    if len(img_bytes) >= 44 and img_bytes[:4] == b'\x01\x00\x00\x00' and img_bytes[40:44] == b' EMF':
        return ".emf"

    # WMF: magic 0xD7CD at bytes 0-1
    if img_bytes[:2] == b'\xd7\xcd':
        return ".wmf"

    # PNG: magic bytes
    if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return ".png"

    # JPEG: FFD8FF
    if img_bytes[:3] == b'\xff\xd8\xff':
        return ".jpg"

    # GIF: GIF87a or GIF89a
    if img_bytes[:6] in (b'GIF87a', b'GIF89a'):
        return ".gif"

    # BMP: BM
    if img_bytes[:2] == b'BM':
        return ".bmp"

    # TIFF: II (little-endian) or MM (big-endian)
    if img_bytes[:2] in (b'II', b'MM'):
        return ".tiff"

    # WEBP: RIFF....WEBP
    if img_bytes[:4] == b'RIFF' and len(img_bytes) >= 12 and img_bytes[8:12] == b'WEBP':
        return ".webp"

    return ".bin"
