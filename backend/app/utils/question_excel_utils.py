import re
import math
import pandas as pd
from typing import Optional, Tuple, Dict, Any

# Column header variations mapping
COLUMN_MAPPING = {
    # Question No
    "question no": "question_no",
    "q.no": "question_no",
    "question number": "question_no",
    "no": "question_no",
    
    # Question Text
    "question text": "question_text",
    "question": "question_text",
    "question title": "question_text",
    
    # Option A
    "option a": "option_a",
    "choice a": "option_a",
    "a": "option_a",
    
    # Option B
    "option b": "option_b",
    "choice b": "option_b",
    "b": "option_b",
    
    # Option C
    "option c": "option_c",
    "choice c": "option_c",
    "c": "option_c",
    
    # Option D
    "option d": "option_d",
    "choice d": "option_d",
    "d": "option_d",
    
    # Correct Option
    "correct option": "correct_option",
    "correct answer": "correct_option",
    "answer": "correct_option",
    
    # Marks
    "marks": "marks",
    "mark": "marks"
}

def normalize_question_column_name(col: Any) -> str:
    if not isinstance(col, str):
        return str(col).strip().lower()
    return col.strip().lower()

def validate_question_required_columns(columns: list) -> Tuple[bool, list]:
    required = ["question_no", "question_text", "option_a", "option_b", "option_c", "option_d", "correct_option", "marks"]
    missing = [req for req in required if req not in columns]
    return len(missing) == 0, missing

def parse_correct_option(value: Any) -> Optional[str]:
    if pd.isna(value):
        return None
    val_str = str(value).strip().upper()
    
    # Convert Option A / Choice A / a / A
    if val_str in ["A", "B", "C", "D"]:
        return val_str
    
    # Check if ends with A, B, C, D
    m = re.match(r"^(OPTION|CHOICE)\s*([A-D])$", val_str)
    if m:
        return m.group(2)
        
    # Check numeric 1, 2, 3, 4
    if val_str in ["1", "1.0"]:
        return "A"
    elif val_str in ["2", "2.0"]:
        return "B"
    elif val_str in ["3", "3.0"]:
        return "C"
    elif val_str in ["4", "4.0"]:
        return "D"
        
    return None

LATEX_MATH_KEYWORDS = [
    r"\frac", r"\sqrt", r"\int", r"\sum", r"\matrix", r"\lim", r"\alpha", r"\beta",
    r"\gamma", r"\delta", r"\theta", r"\pi", r"\infty", r"\cdot", r"\vec", r"\hat",
    r"\le", r"\ge", r"\neq", r"\times", r"\div", r"\pm", r"\partial", r"\Delta", r"\Omega",
    r"\rightarrow", r"\leftarrow", r"\sub", r"\sup", r"\binom", r"\begin{", r"\end{"
]

def normalize_latex_math_in_text(text: str) -> str:
    """
    Detects unwrapped LaTeX math commands (e.g. \\frac{a}{b}, \\sqrt{x}) in text
    and ensures they are enclosed in LaTeX math delimiters \\(...\\) for MathJax.
    """
    if not text:
        return ""
        
    val_str = str(text).strip()
    
    # If text contains math commands but doesn't have $ or \( delimiters
    has_latex_cmd = any(kw in val_str for kw in LATEX_MATH_KEYWORDS)
    has_delimiters = ("$" in val_str) or ("\\(" in val_str) or ("\\[" in val_str)
    
    if has_latex_cmd and not has_delimiters:
        def wrap_match(match):
            m = match.group(0)
            return f" \\({m}\\) "
            
        pattern = r'\\(?:frac|sqrt|int|sum|lim|binom)\{[^{}]*\}(?:\{[^{}]*\})?|\\(?:alpha|beta|gamma|delta|theta|pi|infty|cdot|vec|hat|le|ge|neq|times|div|pm|partial|Delta|Omega|rightarrow|leftarrow)'
        normalized = re.sub(pattern, wrap_match, val_str)
        return normalized.strip()
        
    return val_str

SUB_SUPER_MAP = {
    '₀': '<sub>0</sub>', '₁': '<sub>1</sub>', '₂': '<sub>2</sub>', '₃': '<sub>3</sub>', '₄': '<sub>4</sub>',
    '₅': '<sub>5</sub>', '₆': '<sub>6</sub>', '₇': '<sub>7</sub>', '₈': '<sub>8</sub>', '₉': '<sub>9</sub>',
    '⁰': '<sup>0</sup>', '¹': '<sup>1</sup>', '²': '<sup>2</sup>', '³': '<sup>3</sup>', '⁴': '<sup>4</sup>',
    '⁵': '<sup>5</sup>', '⁶': '<sup>6</sup>', '⁷': '<sup>7</sup>', '⁸': '<sup>8</sup>', '⁹': '<sup>9</sup>',
    '⁺': '<sup>+</sup>', '⁻': '<sup>-</sup>'
}

SYMBOL_FONT_MAP = {
    'Y': 'Ψ', 'y': 'ψ', 'F': 'Φ', 'f': 'φ', 'W': 'Ω', 'w': 'ω',
    'Q': 'Θ', 'q': 'θ', 'L': 'Λ', 'l': 'λ', 'P': 'Π', 'p': 'π',
    'R': 'Ρ', 'r': 'ρ', 'S': 'Σ', 's': 'σ', 'D': 'Δ', 'd': 'δ',
    'G': 'Γ', 'g': 'γ', 'Ñ': '∇'
}

def normalize_chemical_and_math_text(text: str) -> str:
    if not text:
        return ""
    val_str = str(text).strip()
    
    # 1. Repair Symbol font corruptions and math/physics symbols
    val_str = val_str.replace('Ñ2', '∇²').replace('Ñ', '∇')
    val_str = val_str.replace('hbar', 'ħ').replace('hb', 'ħ')
    val_str = val_str.replace('ħ2', 'ħ²')
    val_str = val_str.replace('εo', 'ε₀').replace('ε0', 'ε₀')
    
    # 2. Schrodinger wave equation Y -> Ψ (Psi) wavefunction repair
    if any(k in val_str for k in ['∇', 'Schrodinger', 'ħ', 'hbar', 'E-V', 'E+V', '∇²']):
        val_str = re.sub(r'∇²\s*Y', '∇²Ψ', val_str)
        val_str = re.sub(r'\((E[+-]V)\)\s*Y', r'(\1)Ψ', val_str)
        val_str = re.sub(r'\bY\s*=\s*0\b', 'Ψ = 0', val_str)
        val_str = val_str.replace('ħ2', 'ħ²')
    
    # 3. Degree symbol format: e.g. 45⁰ or 45^0 -> 45°
    val_str = re.sub(r'(\d+)\s*[⁰º]', r'\1°', val_str)
    val_str = re.sub(r'(\d+)\s*\^0', r'\1°', val_str)
    
    # 4. Mass spectrometry chemical ions (e.g. C6H5+, C6H5CH+OH, C6H5CH2O+)
    val_str = re.sub(r'C6H5CH2O\+', 'C₆H₅CH₂O⁺', val_str)
    val_str = re.sub(r'C6H5CH\+OH', 'C₆H₅CH⁺OH', val_str)
    val_str = re.sub(r'C6H5\+', 'C₆H₅⁺', val_str)
    val_str = re.sub(r'C6H5', 'C₆H₅', val_str)
    
    # 5. Scientific exponent notation: e.g. 1023 -> 10²³, 10-24 -> 10⁻²⁴, 1010 -> 10¹⁰, Am2 -> A·m²
    val_str = re.sub(r'(?i)(?<=[x\*\s\d])10\s*-\s*(\d+)', r'10<sup>-\1</sup>', val_str)
    val_str = re.sub(r'(?i)(?<=[x\*\s\d])10\s*(\d{2,3})\b', r'10<sup>\1</sup>', val_str)
    val_str = re.sub(r'Am2\b', 'A·m<sup>2</sup>', val_str)
    
    # 6. Chemical formula subscript auto-converter (e.g. CO2, H2O, C6H12O6, O2, H2, CH4, 2H2O, 2O2, C2H6, H2SO4, HCl, HNO3, NaCl)
    def convert_chem(match):
        s = match.group(0)
        subs = {'0':'₀', '1':'₁', '2':'₂', '3':'₃', '4':'₄', '5':'₅', '6':'₆', '7':'₇', '8':'₈', '9':'₉'}
        res = []
        for i, char in enumerate(s):
            if char.isdigit() and i > 0 and (s[i-1].isalpha() or s[i-1] in subs.values()):
                res.append(subs.get(char, char))
            else:
                res.append(char)
        return "".join(res)
        
    chem_pattern = r'\b(?:[A-Z][a-z]?\d*)+\b'
    val_str = re.sub(chem_pattern, convert_chem, val_str)
    
    # 7. Map unicode subscripts and superscripts to HTML tags
    for char, html_sub in SUB_SUPER_MAP.items():
        if char in val_str:
            val_str = val_str.replace(char, html_sub)
            
    # 8. Merge adjacent sub/sup tags (e.g. <sub>1</sub><sub>2</sub> -> <sub>12</sub>)
    while '<sub>' in val_str and '</sub><sub>' in val_str:
        val_str = re.sub(r'<sub>([^<]+)</sub><sub>([^<]+)</sub>', r'<sub>\1\2</sub>', val_str)
    while '<sup>' in val_str and '</sup><sup>' in val_str:
        val_str = re.sub(r'<sup>([^<]+)</sup><sup>([^<]+)</sup>', r'<sup>\1\2</sup>', val_str)
        
    return normalize_latex_math_in_text(val_str)

def parse_marks(value: Any) -> int:
    if pd.isna(value):
        return 1
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 1

def clean_question_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    val_str = str(value).strip()
    return normalize_chemical_and_math_text(val_str)

def validate_question_row(row: Dict[str, Any], row_no: int, row_images: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], Optional[int]]:
    # 1. Validate question number
    q_no_raw = row.get("question_no")
    if pd.isna(q_no_raw):
        return False, "Question Number (Question No) is missing or empty.", None
    try:
        q_no = int(float(q_no_raw))
        if q_no <= 0:
            return False, f"Question Number must be a positive integer, got {q_no}.", None
    except (ValueError, TypeError):
        return False, f"Question Number must be a valid integer, got '{q_no_raw}'.", None

    row_imgs = row_images or {}

    # 2. Validate question text (valid if text present OR image present)
    q_text = clean_question_text(row.get("question_text"))
    if not q_text and not row_imgs.get("question_text"):
        return False, "Question Text is empty.", q_no

    # 3. Validate options (valid if text present OR image present)
    opt_a = clean_question_text(row.get("option_a"))
    opt_b = clean_question_text(row.get("option_b"))
    opt_c = clean_question_text(row.get("option_c"))
    opt_d = clean_question_text(row.get("option_d"))
    
    if not opt_a and not row_imgs.get("option_a"):
        return False, "Option A is empty.", q_no
    if not opt_b and not row_imgs.get("option_b"):
        return False, "Option B is empty.", q_no
    if not opt_c and not row_imgs.get("option_c"):
        return False, "Option C is empty.", q_no
    if not opt_d and not row_imgs.get("option_d"):
        return False, "Option D is empty.", q_no

    # 4. Validate correct option
    correct = parse_correct_option(row.get("correct_option"))
    if not correct:
        return False, f"Correct Option must be A, B, C, or D (or 1, 2, 3, 4), got '{row.get('correct_option')}'.", q_no

    return True, None, q_no


def detect_duplicate_question_numbers(df: pd.DataFrame) -> Tuple[bool, list]:
    # Given normalized column names, find duplicates in question_no
    if "question_no" not in df.columns:
        return False, []
    
    # Filter rows with valid integers for question_no to do check
    valid_q_nos = []
    for val in df["question_no"]:
        try:
            if not pd.isna(val):
                valid_q_nos.append(int(float(val)))
        except (ValueError, TypeError):
            pass
            
    seen = set()
    dups = set()
    for q in valid_q_nos:
        if q in seen:
            dups.add(q)
        else:
            seen.add(q)
            
    return len(dups) > 0, list(dups)

def supports_unicode_text(value: Any) -> bool:
    """Helper to check if string contains characters that need full unicode encoding (e.g. Tamil or math formulas)"""
    if not isinstance(value, str):
        return False
    # Tamil character unicode range: U+0B80 to U+0BFF
    # Math symbols / LaTeX range can contain \, ^, _, {, }, etc.
    tamil_match = re.search(r"[\u0b80-\u0bff]", value)
    math_match = re.search(r"[\$\\int\\frac\\sqrt\^_\{\}]", value)
    return bool(tamil_match or math_match)
