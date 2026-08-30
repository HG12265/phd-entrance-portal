import re
import os
import datetime
import pandas as pd
from typing import Optional, List, Dict, Any

PHOTO_DIR = os.path.join("uploads", "candidate_photos")

def normalize_column_name(col: str) -> str:
    """Normalize and map common variants of column names to required keys."""
    if not col or pd.isna(col):
        return ""
    col_str = str(col).strip().lower()
    
    # Remove extra interior whitespaces/underscores
    col_str = col_str.replace("_", " ")
    col_str = re.sub(r'\s+', ' ', col_str)
    
    # Match variants
    if col_str in ["name", "candidate name", "full name", "candidate_name", "applicant name", "applicant_name"]:
        return "applicant_name"
    elif col_str in ["application number", "application_number", "app no", "application no", "register no", "register number", "application id", "application_id", "app id"]:
        return "application_id"
    elif col_str in ["mail id", "mail_id", "email", "email id", "mail", "mailid"]:
        return "email"
    elif col_str in ["applied subject", "applied_subject", "subject"]:
        return "subject"
    elif col_str in ["dob", "date of birth", "birth date", "date_of_birth", "d.o.b"]:
        return "dob"
    elif col_str in ["mobile number", "mobile_number", "mobile", "phone", "phone number", "contact number"]:
        return "mobile_number"
    elif col_str in ["session", "exam session", "exam_session", "batch"]:
        return "exam_session"
    elif col_str in ["initial", "initials"]:
        return "initial"
    elif col_str in ["category (ft/pt)", "category", "ft/pt", "mode", "category_ft_pt"]:
        return "category_ft_pt"
    elif col_str in ["programme offered", "program offered", "programme", "program", "programme_offered"]:
        return "programme_offered"
    elif col_str in ["department", "applied department"]:
        return "department"
    
    return col_str.replace(" ", "_")

def find_header_row(df_first_rows: List[List[Any]]) -> int:
    """
    Scans first 20 rows of the Excel sheet.
    Accepts a row as header only if it contains at least 4 recognized candidate headers.
    Returns the 0-indexed row number of the header row, or -1 if not found.
    """
    recognized_headers = {
        "application_id", "applicant_name", "dob", "department", 
        "mobile_number", "email", "initial", "category_ft_pt", 
        "programme_offered", "subject", "exam_session"
    }

    for i, row in enumerate(df_first_rows):
        match_count = 0
        for item in row:
            if pd.isna(item) or item is None:
                continue
            normalized = normalize_column_name(str(item).strip())
            if normalized in recognized_headers:
                match_count += 1
        if match_count >= 4:
            return i
    return -1

def validate_required_columns(df_columns: List[str], required_columns: List[str]) -> List[str]:
    """Check for missing columns from the required list."""
    missing = []
    for rc in required_columns:
        if rc not in df_columns:
            missing.append(rc)
    return missing

def parse_dob(value: Any) -> Optional[datetime.date]:
    """Parse date of birth from strings, datetime objects, or Excel serial numbers."""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
        
    val_str = str(value).strip()
    
    # Check if time component is appended and strip it
    if " " in val_str:
        val_str = val_str.split(" ")[0]
        
    # Check Excel Serial Date
    try:
        if val_str.replace('.', '', 1).isdigit():
            val_float = float(val_str)
            if 10000 < val_float < 100000:
                dt = pd.to_datetime(val_float, unit='D', origin='1899-12-30')
                return dt.date()
    except Exception:
        pass

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%b-%d-%Y",
        "%B-%d-%Y"
    ]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(val_str, fmt)
            return dt.date()
        except ValueError:
            continue
            
    # Last fallback try pandas to_datetime
    try:
        dt = pd.to_datetime(val_str)
        return dt.date()
    except Exception:
        pass
        
    return None

def validate_email(email: Any) -> bool:
    """Validate email format."""
    if pd.isna(email) or email is None:
        return True  # Nullable
    email_str = str(email).strip()
    if not email_str:
        return True
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email_str))

def validate_mobile(mobile: Any) -> bool:
    """Validate mobile phone format."""
    if pd.isna(mobile) or mobile is None:
        return True  # Nullable
    mob_str = str(mobile).strip()
    if not mob_str:
        return True
    # Strip spaces, hyphens, brackets, and + sign
    clean_mob = re.sub(r'[\s\-\+\(\)]', '', mob_str)
    return clean_mob.isdigit() and len(clean_mob) >= 8

def generate_photo_filename(application_number: str) -> str:
    """Replace '/' with '-' to get the base photo filename."""
    if not application_number:
        return ""
    return str(application_number).strip().replace("/", "-")

def find_candidate_photo(application_id: str) -> Dict[str, Any]:
    """Check candidate_photos folder for matching application ID photo with variants support."""
    if not application_id:
        return {
            "photo_filename": None,
            "photo_path": None,
            "photo_status": "missing"
        }
        
    app_id_clean = str(application_id).strip()
    
    # 1. replace "/" with "-"
    base_standard = app_id_clean.replace("/", "-")
    
    # 2. support variant where CETPHD becomes CET-PHD
    base_variant = base_standard
    if base_standard.startswith("CETPHD-"):
        base_variant = "CET-PHD-" + base_standard[7:]
    elif base_standard.startswith("CET-PHD-"):
        base_variant = "CETPHD-" + base_standard[8:]
        
    bases = [base_standard]
    if base_variant != base_standard:
        bases.append(base_variant)
        
    extensions = [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]
    
    os.makedirs(PHOTO_DIR, exist_ok=True)
    
    for base in bases:
        for ext in extensions:
            filename = f"{base}{ext}"
            local_path = os.path.join(PHOTO_DIR, filename)
            if os.path.exists(local_path):
                return {
                    "photo_filename": filename,
                    "photo_path": f"/static/candidate_photos/{filename}",
                    "photo_status": "available"
                }
                
    return {
        "photo_filename": None,
        "photo_path": None,
        "photo_status": "missing"
    }

def resolve_candidate_department(dep_str: str, sub_str: str, depts) -> dict:
    """Resolve department mapping dynamically following priority rules."""
    dep_str = str(dep_str).strip() if dep_str and not pd.isna(dep_str) else ""
    sub_str = str(sub_str).strip() if sub_str and not pd.isna(sub_str) else ""
    
    # Common variations and aliases mapping
    aliases = {
        "food science technology and nutrition": "Food Science Technology and Nutrition",
        "food science, technology and nutrition": "Food Science Technology and Nutrition",
        "food science and nutrition": "Food Science Technology and Nutrition",
        "management studies": "Management",
    }
    
    dep_lower = dep_str.lower()
    if dep_lower in aliases:
        dep_str = aliases[dep_lower]
        
    sub_lower = sub_str.lower()
    if sub_lower in aliases:
        sub_str = aliases[sub_lower]
    
    # Rule 1: Department exact name
    if dep_str:
        for d in depts:
            if d.department_name == dep_str:
                return {"id": d.id, "error": None}
                
    # Rule 2: Department code exact
    if dep_str:
        for d in depts:
            if d.department_code == dep_str:
                return {"id": d.id, "error": None}
                
    # Rule 3: Department case-insensitive trimmed
    if dep_str:
        dep_lower = dep_str.lower()
        for d in depts:
            if d.department_name.strip().lower() == dep_lower:
                return {"id": d.id, "error": None}
            if d.department_code.strip().lower() == dep_lower:
                return {"id": d.id, "error": None}
                
    # Rule 4: Subject exact name
    if sub_str:
        for d in depts:
            if d.department_name == sub_str:
                return {"id": d.id, "error": None}
                
    # Rule 5: Subject code exact
    if sub_str:
        for d in depts:
            if d.department_code == sub_str:
                return {"id": d.id, "error": None}
                
    # Rule 6: Unique contains match
    for text_val in (dep_str, sub_str):
        if not text_val:
            continue
        text_lower = text_val.lower()
        contains_matches = []
        for d in depts:
            d_name_lower = d.department_name.strip().lower()
            d_code_lower = d.department_code.strip().lower()
            if text_lower in d_name_lower or d_name_lower in text_lower:
                contains_matches.append(d)
            elif text_lower in d_code_lower:
                contains_matches.append(d)
                
        if len(contains_matches) == 1:
            return {"id": contains_matches[0].id, "error": None}
        elif len(contains_matches) > 1:
            # If multiple contains matches exist, verify if one exact matches
            exact_matches = [d for d in contains_matches if d.department_name.strip().lower() == text_lower or d.department_code.strip().lower() == text_lower]
            if len(exact_matches) == 1:
                return {"id": exact_matches[0].id, "error": None}
            return {"id": None, "error": "Department mapping ambiguous"}
            
    return {"id": None, "error": "Department not found"}
