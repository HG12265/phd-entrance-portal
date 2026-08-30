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

def parse_marks(value: Any) -> int:
    if pd.isna(value):
        return 1
    try:
        # Convert float like 1.0 to 1
        return int(float(value))
    except (ValueError, TypeError):
        return 1

def clean_question_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    val_str = str(value).strip()
    # Check if decimal float representations of integer exists, clean up (though not typical for question text)
    return val_str

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
