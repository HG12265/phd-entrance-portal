"""
ole_extractor.py

Extracts content from OLE compound document objects embedded in Excel files.
These include MathType equations and Microsoft Equation Editor objects.

OLE objects can contain:
1. OMML XML in the WordDocument stream (newer Equation Editor)
2. EMF/WMF preview in the CONTENTS stream (visual representation)
3. MathType binary (MTEF format) — complex, extract preview only

Uses the 'olefile' library for OLE parsing.
Falls back gracefully if olefile is not installed.
"""

import io
import logging
import struct
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger("phd_app")


@dataclass
class OLEContent:
    """Content extracted from an OLE compound document."""
    omml_xml: Optional[str] = None       # Office Math XML if found
    preview_bytes: Optional[bytes] = None  # EMF/WMF preview bytes if found
    preview_format: str = ""              # "emf" or "wmf" or ""
    mathtype_detected: bool = False       # True if MathType MTEF stream found
    equation_editor_detected: bool = False  # True if MS Equation Editor found
    extraction_method: str = ""          # "omml", "emf_preview", "wmf_preview", "failed"
    error: str = ""


# OLE CLSID values for known equation editors
# MathType CLSID: {0002CE02-0000-0000-C000-000000000046}
MATHTYPE_CLSID = b'\x02\xce\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46'
# MS Equation Editor 3.x CLSID: {0003000B-0000-0000-C000-000000000046}
EQUATION_EDITOR_CLSID = b'\x0b\x00\x03\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46'


def extract_ole_content(ole_bytes: bytes) -> OLEContent:
    """
    Extract mathematical content from OLE binary data.

    Tries:
    1. Parse as OLE compound document with olefile
    2. Look for OMML stream (newer Equation Editor)
    3. Look for EMF/WMF preview in CONTENTS or OlePres streams
    4. Detect MathType MTEF stream (extract EMF preview if available)

    Returns OLEContent with whatever was extractable.
    """
    if not ole_bytes or len(ole_bytes) < 8:
        return OLEContent(error="Empty or too-small OLE data")

    # Check OLE magic header: D0 CF 11 E0 A1 B1 1A E1
    ole_magic = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    if not ole_bytes.startswith(ole_magic):
        # Not an OLE file — might be a direct EMF/WMF or other format
        # Try to detect EMF magic: 01 00 00 00 ... 20 45 4D 46 (signature " EMF")
        if len(ole_bytes) >= 88:
            # EMF signature at offset 40
            if ole_bytes[40:44] == b' EMF':
                return OLEContent(
                    preview_bytes=ole_bytes,
                    preview_format="emf",
                    extraction_method="emf_preview",
                )
        return OLEContent(error="Not an OLE compound document and not a direct EMF/WMF")

    try:
        import olefile
    except ImportError:
        # olefile not installed — try raw scanning
        return _raw_scan_ole(ole_bytes)

    try:
        ole_stream = io.BytesIO(ole_bytes)
        ole = olefile.OleFileIO(ole_stream)

        result = OLEContent()

        # Check CLSID for known equation editor types
        root_clsid = ole.root.clsid if ole.root else None
        if root_clsid:
            clsid_bytes = _parse_clsid(root_clsid)
            if clsid_bytes == MATHTYPE_CLSID:
                result.mathtype_detected = True
                logger.debug("OLE: MathType object detected")
            elif clsid_bytes == EQUATION_EDITOR_CLSID:
                result.equation_editor_detected = True
                logger.debug("OLE: MS Equation Editor object detected")

        # 1. Try to extract OMML from 'Equation' or 'WordDocument' stream
        omml_result = _try_extract_omml(ole)
        if omml_result:
            result.omml_xml = omml_result
            result.extraction_method = "omml"
            logger.info("OLE: Successfully extracted OMML XML")

        # 2. Try to extract EMF/WMF preview from OLE presentation streams
        preview_bytes, preview_fmt = _try_extract_emf_preview(ole)
        if preview_bytes:
            result.preview_bytes = preview_bytes
            result.preview_format = preview_fmt
            if not result.extraction_method:
                result.extraction_method = f"{preview_fmt}_preview"
            logger.info(f"OLE: Successfully extracted {preview_fmt.upper()} preview ({len(preview_bytes)} bytes)")

        # 3. MathType: try MTEF stream → may contain EMF preview
        if result.mathtype_detected and not preview_bytes:
            mtef_preview = _try_mathtype_preview(ole)
            if mtef_preview:
                result.preview_bytes = mtef_preview[0]
                result.preview_format = mtef_preview[1]
                if not result.extraction_method:
                    result.extraction_method = f"{mtef_preview[1]}_preview"

        if not result.extraction_method:
            result.extraction_method = "failed"
            result.error = "No extractable content found in OLE object"

        ole.close()
        return result

    except Exception as e:
        logger.warning(f"OLE extraction failed: {type(e).__name__}: {e}")
        return OLEContent(
            error=f"OLE parsing failed: {type(e).__name__}: {str(e)}",
            extraction_method="failed"
        )


def _parse_clsid(clsid_str: str) -> bytes:
    """Convert CLSID string representation to bytes for comparison."""
    try:
        # olefile returns CLSID as hex string like "00020CE0-0000-0000-C000-000000000046"
        hex_str = clsid_str.replace("-", "").replace("{", "").replace("}", "")
        return bytes.fromhex(hex_str)
    except Exception:
        return b""


def _try_extract_omml(ole) -> Optional[str]:
    """
    Try to extract OMML (Office Math XML) from OLE streams.
    Newer versions of Equation Editor store OMML in a dedicated stream.
    """
    candidate_streams = [
        ['Equation Native'],
        ['MathType', 'Equation'],
        ['Object Pool'],
        ['CONTENTS'],
    ]

    # Scan all streams for XML content that looks like OMML
    try:
        for entry in ole.listdir(streams=True, storages=False):
            stream_name = '/'.join(entry)
            try:
                data = ole.openstream(entry).read()
                if not data:
                    continue
                # Look for OMML namespace markers
                if b'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"' in data or \
                   b'<m:oMath' in data or b'<m:oMathPara' in data:
                    # Found OMML-like content
                    start = data.find(b'<m:')
                    if start >= 0:
                        xml_chunk = data[start:]
                        return xml_chunk.decode('utf-8', errors='replace')
            except Exception:
                continue
    except Exception:
        pass

    return None


def _try_extract_emf_preview(ole) -> Tuple[Optional[bytes], str]:
    """
    Try to extract EMF or WMF preview from OLE presentation streams.
    Office stores visual previews in streams like '\x01Ole10Native' or 'CONTENTS'.
    """
    # EMF signature: first 4 bytes = 01 00 00 00, bytes 40-44 = " EMF"
    # WMF signature: first 2 bytes = D7 CD (WMF magic)
    EMF_SIG_40 = b' EMF'  # at offset 40 in EMF header
    WMF_MAGIC = b'\xd7\xcd'  # WMF magic
    EMF_MAGIC_4 = b'\x01\x00\x00\x00'  # EMF: iType=1 (EMR_HEADER)

    preview_streams_priority = [
        '\x01Ole10Native',
        'CONTENTS',
        '\x01CompObj',
        '\x03ObjInfo',
    ]

    def detect_format(data: bytes) -> str:
        if len(data) >= 44 and data[40:44] == EMF_SIG_40:
            return "emf"
        if len(data) >= 2 and data[:2] == WMF_MAGIC:
            return "wmf"
        if len(data) >= 4 and data[:4] == EMF_MAGIC_4 and len(data) >= 44:
            # Might be EMF — check signature deeper
            return "emf"
        return ""

    try:
        for entry in ole.listdir(streams=True, storages=False):
            stream_key = '/'.join(str(e) for e in entry)
            stream_name = entry[-1] if entry else ""

            # Check if stream name is in priority list or has 'native' in name
            is_priority = (
                stream_name in preview_streams_priority or
                'native' in stream_name.lower() or
                'contents' in stream_name.lower()
            )

            if not is_priority:
                continue

            try:
                data = ole.openstream(entry).read()
                if not data or len(data) < 10:
                    continue

                # Ole10Native has a 4-byte size header we need to skip
                if stream_name == '\x01Ole10Native' and len(data) > 4:
                    size = struct.unpack_from('<I', data, 0)[0]
                    if size < len(data) - 4:
                        data = data[4:4 + size]

                fmt = detect_format(data)
                if fmt:
                    return data, fmt

                # Try scanning through the stream for EMF/WMF signature
                for offset in range(0, min(len(data) - 44, 512)):
                    if data[offset:offset+4] == EMF_MAGIC_4 and data[offset+40:offset+44] == EMF_SIG_40:
                        return data[offset:], "emf"
                    if data[offset:offset+2] == WMF_MAGIC:
                        return data[offset:], "wmf"

            except Exception:
                continue

    except Exception as e:
        logger.debug(f"OLE EMF/WMF extraction scan error: {e}")

    return None, ""


def _try_mathtype_preview(ole) -> Optional[Tuple[bytes, str]]:
    """
    Try to extract a visual preview from a MathType OLE object.
    MathType stores equations in MTEF format (proprietary binary).
    We try to get the EMF preview that Office generates when embedding.
    """
    try:
        for entry in ole.listdir(streams=True, storages=False):
            stream_name = entry[-1] if entry else ""
            if 'pres' in stream_name.lower() or 'metafile' in stream_name.lower() or \
               stream_name == '\x02OlePres000':
                try:
                    data = ole.openstream(entry).read()
                    if data and len(data) > 40:
                        # Check for EMF or WMF
                        if data[40:44] == b' EMF':
                            return data, "emf"
                        if data[:2] == b'\xd7\xcd':
                            return data, "wmf"
                except Exception:
                    continue
    except Exception:
        pass

    return None


def _raw_scan_ole(data: bytes) -> OLEContent:
    """
    Last-resort: scan raw bytes for embedded EMF/WMF signatures
    without using olefile.
    """
    EMF_SIG_40 = b' EMF'
    WMF_MAGIC = b'\xd7\xcd'
    EMF_MAGIC_4 = b'\x01\x00\x00\x00'

    # Scan for EMF signature
    for i in range(0, min(len(data) - 44, 2048)):
        if data[i:i+4] == EMF_MAGIC_4 and data[i+40:i+44] == EMF_SIG_40:
            return OLEContent(
                preview_bytes=data[i:],
                preview_format="emf",
                extraction_method="emf_preview"
            )

    # Scan for WMF signature
    for i in range(0, min(len(data) - 4, 2048)):
        if data[i:i+2] == WMF_MAGIC:
            return OLEContent(
                preview_bytes=data[i:],
                preview_format="wmf",
                extraction_method="wmf_preview"
            )

    return OLEContent(error="No EMF/WMF content found in raw scan", extraction_method="failed")
