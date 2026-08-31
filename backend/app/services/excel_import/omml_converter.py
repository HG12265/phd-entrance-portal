"""
omml_converter.py

Converts OMML (Office Math Markup Language / OfficeMath XML) to LaTeX.

OMML is the XML format used by Microsoft Office 2007+ for math equations.
It can appear in:
- OLE objects containing Equation Editor 3+ equations
- Direct cell XML in some xlsx files with embedded math

Conversion approach:
1. Primary: XSLT-based conversion using the omml2latex.xsl stylesheet
   (lxml required for XSLT processing)
2. Fallback: Simple rule-based text extraction (produces approximate LaTeX)

The output LaTeX is wrapped in \\( ... \\) for MathJax inline rendering
or \\[ ... \\] for block rendering.
"""

import os
import re
import logging
from typing import Optional

logger = logging.getLogger("phd_app")

# Path to XSLT stylesheet (same directory as this file)
XSLT_PATH = os.path.join(os.path.dirname(__file__), "omml2latex.xsl")


def omml_to_latex(omml_xml: str, display_mode: bool = False) -> Optional[str]:
    """
    Convert OMML XML to LaTeX string.

    Args:
        omml_xml: OMML XML string (may be a fragment or full document)
        display_mode: If True, wraps in \\[ \\]; if False, wraps in \\( \\)

    Returns:
        LaTeX string or None if conversion failed
    """
    if not omml_xml or not omml_xml.strip():
        return None

    # Clean up the OMML XML
    omml_clean = _normalize_omml(omml_xml)
    if not omml_clean:
        return None

    # Try XSLT conversion first
    latex = _xslt_convert(omml_clean)
    if latex:
        wrapper_open = r"\[" if display_mode else r"\("
        wrapper_close = r"\]" if display_mode else r"\)"
        return f"{wrapper_open}{latex}{wrapper_close}"

    # Fallback: simple text extraction
    text = _simple_text_extract(omml_clean)
    if text:
        logger.info("omml_converter: Used simple text extraction fallback")
        wrapper_open = r"\[" if display_mode else r"\("
        wrapper_close = r"\]" if display_mode else r"\)"
        return f"{wrapper_open}{text}{wrapper_close}"

    return None


def _normalize_omml(xml_str: str) -> Optional[str]:
    """
    Ensure the OMML XML has proper namespace declarations and is well-formed.
    Returns cleaned XML string or None.
    """
    xml_str = xml_str.strip()

    # Add OMML namespace if missing
    OMML_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
    W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    R_NS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'

    # Wrap bare fragments
    if not xml_str.startswith("<?xml") and not xml_str.startswith("<m:"):
        if "<m:" in xml_str:
            # Wrap in a container with namespaces
            xml_str = (
                f'<m:oMathPara {OMML_NS} {W_NS} {R_NS}>'
                f'{xml_str}'
                f'</m:oMathPara>'
            )

    # Add XML declaration if missing
    if not xml_str.startswith("<?xml"):
        xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

    # Basic well-formedness check
    if not ('<m:' in xml_str or 'oMath' in xml_str):
        return None

    return xml_str


def _xslt_convert(omml_xml: str) -> Optional[str]:
    """
    Convert OMML to LaTeX using XSLT stylesheet.
    Requires: lxml, omml2latex.xsl
    """
    if not os.path.exists(XSLT_PATH):
        logger.debug("omml_converter: XSLT stylesheet not found at %s", XSLT_PATH)
        return None

    try:
        from lxml import etree

        omml_doc = etree.fromstring(omml_xml.encode('utf-8'))
        xslt_doc = etree.parse(XSLT_PATH)
        transform = etree.XSLT(xslt_doc)
        result = transform(omml_doc)
        latex = str(result).strip()

        if latex and len(latex) > 1:
            # Clean up common XSLT output artifacts
            latex = latex.replace('\n', ' ').replace('  ', ' ').strip()
            return latex

    except ImportError:
        logger.debug("omml_converter: lxml not available, cannot do XSLT conversion")
    except Exception as e:
        logger.debug(f"omml_converter: XSLT conversion failed: {e}")

    return None


def _simple_text_extract(xml_str: str) -> Optional[str]:
    """
    Simple rule-based OMML → LaTeX approximation.
    Not perfect, but provides readable output when XSLT is unavailable.

    Handles common math elements:
    - m:t (text runs) -> literal text
    - m:r (math runs) -> literal text
    - m:f (fraction) -> \\frac{num}{den}
    - m:rad (radical) -> \\sqrt{...}
    - m:sup (superscript) -> ^{...}
    - m:sub (subscript) -> _{...}
    - m:limLow (limit lower) -> \\lim_{...}
    - m:nary (n-ary like integral) -> \\int or \\sum
    - m:d (delimiter) -> ( ... )
    - m:m (matrix) -> \\begin{pmatrix}...\\end{pmatrix}
    """
    try:
        from lxml import etree as ET
        doc = ET.fromstring(xml_str.encode('utf-8'))
        return _node_to_latex(doc)
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: strip XML tags and return plain text
    try:
        plain = re.sub(r'<[^>]+>', '', xml_str)
        plain = re.sub(r'\s+', ' ', plain).strip()
        if plain:
            return plain
    except Exception:
        pass

    return None


def _node_to_latex(node, ns_prefix: str = "m") -> str:
    """Recursively convert OMML XML node to LaTeX string."""
    OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    tag = node.tag.split('}')[-1] if '}' in node.tag else node.tag

    def children_latex():
        return "".join(_node_to_latex(child) for child in node)

    def child_by_tag(parent, tag_name):
        for child in parent:
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == tag_name:
                return child
        return None

    def child_text(parent, tag_name):
        child = child_by_tag(parent, tag_name)
        if child is not None:
            return _node_to_latex(child)
        return ""

    # Text content node
    if tag in ('t', 'r'):
        text = node.text or ''
        for child in node:
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == 't':
                text += child.text or ''
        return text

    # Fraction: \frac{num}{den}
    elif tag == 'f':
        num_node = child_by_tag(node, 'num')
        den_node = child_by_tag(node, 'den')
        num = _node_to_latex(num_node) if num_node is not None else ''
        den = _node_to_latex(den_node) if den_node is not None else ''
        return fr'\frac{{{num}}}{{{den}}}'

    # Radical: \sqrt{...} or \sqrt[n]{...}
    elif tag == 'rad':
        deg_node = child_by_tag(node, 'deg')
        e_node = child_by_tag(node, 'e')
        deg = _node_to_latex(deg_node) if deg_node is not None else ''
        base = _node_to_latex(e_node) if e_node is not None else ''
        if deg and deg.strip():
            return fr'\sqrt[{deg}]{{{base}}}'
        return fr'\sqrt{{{base}}}'

    # Superscript
    elif tag == 'sSup':
        e_node = child_by_tag(node, 'e')
        sup_node = child_by_tag(node, 'sup')
        base = _node_to_latex(e_node) if e_node is not None else ''
        sup = _node_to_latex(sup_node) if sup_node is not None else ''
        return f'{base}^{{{sup}}}'

    # Subscript
    elif tag == 'sSub':
        e_node = child_by_tag(node, 'e')
        sub_node = child_by_tag(node, 'sub')
        base = _node_to_latex(e_node) if e_node is not None else ''
        sub = _node_to_latex(sub_node) if sub_node is not None else ''
        return f'{base}_{{{sub}}}'

    # Sub-superscript
    elif tag == 'sSubSup':
        e_node = child_by_tag(node, 'e')
        sub_node = child_by_tag(node, 'sub')
        sup_node = child_by_tag(node, 'sup')
        base = _node_to_latex(e_node) if e_node is not None else ''
        sub = _node_to_latex(sub_node) if sub_node is not None else ''
        sup = _node_to_latex(sup_node) if sup_node is not None else ''
        return f'{base}_{{{sub}}}^{{{sup}}}'

    # Limit (lower): \lim_{x \to 0}
    elif tag == 'limLow':
        e_node = child_by_tag(node, 'e')
        lim_node = child_by_tag(node, 'lim')
        base = _node_to_latex(e_node) if e_node is not None else r'\lim'
        lim = _node_to_latex(lim_node) if lim_node is not None else ''
        return fr'{base}_{{{lim}}}'

    # N-ary (integral, sum, product)
    elif tag == 'nary':
        # Try to get the operator character from naryPr
        pr_node = child_by_tag(node, 'naryPr')
        operator = r'\int'
        if pr_node is not None:
            chr_node = child_by_tag(pr_node, 'chr')
            if chr_node is not None:
                chr_val = chr_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
                if chr_val:
                    char_map = {
                        '∑': r'\sum', '∏': r'\prod', '∫': r'\int',
                        '∬': r'\iint', '∭': r'\iiint', '∮': r'\oint',
                        'Σ': r'\sum', 'Π': r'\prod',
                    }
                    operator = char_map.get(chr_val, r'\int')

        sub_node = child_by_tag(node, 'sub')
        sup_node = child_by_tag(node, 'sup')
        e_node = child_by_tag(node, 'e')
        sub = _node_to_latex(sub_node) if sub_node is not None else ''
        sup = _node_to_latex(sup_node) if sup_node is not None else ''
        body = _node_to_latex(e_node) if e_node is not None else ''
        result = operator
        if sub:
            result += f'_{{{sub}}}'
        if sup:
            result += f'^{{{sup}}}'
        result += f' {body}'
        return result

    # Delimiter: ( ... ) [ ... ] { ... }
    elif tag == 'd':
        pr_node = child_by_tag(node, 'dPr')
        open_char = '('
        close_char = ')'
        if pr_node is not None:
            beg_node = child_by_tag(pr_node, 'begChr')
            end_node = child_by_tag(pr_node, 'endChr')
            if beg_node is not None:
                open_char = beg_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '(')
            if end_node is not None:
                close_char = end_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', ')')

        inner_parts = []
        for child in node:
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == 'e':
                inner_parts.append(_node_to_latex(child))
        inner = r' \middle| '.join(inner_parts) if len(inner_parts) > 1 else (inner_parts[0] if inner_parts else '')
        return fr'\left{open_char} {inner} \right{close_char}'

    # Matrix
    elif tag == 'm':
        rows_latex = []
        for child in node:
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == 'mr':
                cells = []
                for cell in child:
                    cell_tag = cell.tag.split('}')[-1] if '}' in cell.tag else cell.tag
                    if cell_tag == 'e':
                        cells.append(_node_to_latex(cell))
                rows_latex.append(' & '.join(cells))
        matrix_body = r' \\ '.join(rows_latex)
        return fr'\begin{{pmatrix}} {matrix_body} \end{{pmatrix}}'

    # Function (like sin, cos, etc.)
    elif tag == 'func':
        fname_node = child_by_tag(node, 'fName')
        e_node = child_by_tag(node, 'e')
        fname = _node_to_latex(fname_node) if fname_node is not None else ''
        arg = _node_to_latex(e_node) if e_node is not None else ''
        return f'{fname}{{{arg}}}'

    # Group characters (e.g. overline, underline)
    elif tag == 'groupChr':
        e_node = child_by_tag(node, 'e')
        pr_node = child_by_tag(node, 'groupChrPr')
        body = _node_to_latex(e_node) if e_node is not None else ''
        if pr_node is not None:
            chr_node = child_by_tag(pr_node, 'chr')
            if chr_node is not None:
                chr_val = chr_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '')
                if chr_val in ('⃗', '→'):
                    return fr'\vec{{{body}}}'
                elif chr_val in ('̄', '‾'):
                    return fr'\overline{{{body}}}'
                elif chr_val in ('̂',):
                    return fr'\hat{{{body}}}'
        return body

    # Accent (hat, tilde, etc.)
    elif tag == 'acc':
        e_node = child_by_tag(node, 'e')
        pr_node = child_by_tag(node, 'accPr')
        body = _node_to_latex(e_node) if e_node is not None else ''
        if pr_node is not None:
            chr_node = child_by_tag(pr_node, 'chr')
            if chr_node is not None:
                chr_val = chr_node.get('{http://schemas.openxmlformats.org/officeDocument/2006/math}val', '^')
                acc_map = {
                    '^': fr'\hat{{{body}}}',
                    '~': fr'\tilde{{{body}}}',
                    '`': fr'\grave{{{body}}}',
                    '´': fr'\acute{{{body}}}',
                    '⃗': fr'\vec{{{body}}}',
                    '→': fr'\vec{{{body}}}',
                    '¨': fr'\ddot{{{body}}}',
                    '·': fr'\dot{{{body}}}',
                }
                return acc_map.get(chr_val, body)
        return fr'\hat{{{body}}}'

    # Properties nodes (skip, they affect appearance not content)
    elif tag.endswith('Pr') or tag in ('ctrlPr', 'rPr', 'pPr', 'bookmarkStart', 'bookmarkEnd'):
        return ''

    # Default: recurse into children
    else:
        return children_latex()
