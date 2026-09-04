import os
import re
import uuid
import json
import shutil
import math
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.import_log import ImportLog
from app.models.admin import AdminUser
from app.schemas.candidate_schema import CandidateResponse, CandidateListResponse, CandidateUploadSummary, CandidateManualCreate
from app.utils.auth_dependency import get_current_admin
from app.utils.excel_utils import (
    normalize_column_name,
    find_header_row,
    validate_required_columns,
    parse_dob,
    validate_email,
    validate_mobile,
    find_candidate_photo,
    generate_photo_filename,
    resolve_candidate_department
)

router = APIRouter()

EXCEL_DIR = os.path.join("uploads", "candidate_excels")
PHOTO_DIR = os.path.join("uploads", "candidate_photos")

# Ensure directories exist
os.makedirs(EXCEL_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)

def process_candidate_payload(
    db: Session,
    payload_dict: dict,
    depts: list,
    active_sessions: list,
    excel_duplicates_tracker: set,
    is_manual: bool = False
) -> dict:
    """
    Standardizes and validates candidate payload for both manual add and Excel upload.
    Returns:
        {"candidate": Candidate, "error": None} or {"candidate": None, "error": str}
    """
    # 1. Resolve Application ID
    app_id = payload_dict.get("application_id")
    if not app_id:
        app_id = payload_dict.get("application_number")
        
    app_id_str = str(app_id).strip() if app_id and not pd.isna(app_id) else ""
    if not app_id_str:
        return {"candidate": None, "error": "Application ID cannot be empty."}
        
    # Check duplicate in current request/excel tracker
    if app_id_str in excel_duplicates_tracker:
        return {"candidate": None, "error": "Duplicate Application ID.", "app_id": app_id_str}
        
    # Check duplicate in database
    existing_db = db.query(Candidate).filter(
        (Candidate.application_id == app_id_str) | (Candidate.application_number == app_id_str)
    ).first()
    if existing_db:
        return {"candidate": None, "error": "Duplicate Application ID.", "app_id": app_id_str}
        
    # 2. Resolve Applicant Name & Initial
    applicant_name = payload_dict.get("applicant_name")
    if not applicant_name:
        applicant_name = payload_dict.get("name")
        
    applicant_name_str = str(applicant_name).strip() if applicant_name and not pd.isna(applicant_name) else ""
    if not applicant_name_str:
        return {"candidate": None, "error": "Applicant Name cannot be empty.", "app_id": app_id_str}
        
    initial = payload_dict.get("initial")
    initial_str = str(initial).strip() if initial and not pd.isna(initial) else ""
    
    # Combined name = Applicant Name + Initial
    if initial_str:
        name_str = f"{applicant_name_str} {initial_str}"
    else:
        name_str = applicant_name_str
        
    # 3. Resolve Date of Birth
    dob_val = payload_dict.get("dob")
    parsed_dob = parse_dob(dob_val)
    if not parsed_dob:
        return {"candidate": None, "error": f"Invalid Date of Birth format: '{dob_val}'. Accepted formats: DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD.", "app_id": app_id_str}
        
    # 4. Resolve Department & Subject
    dept_val = payload_dict.get("department")
    subject_val = payload_dict.get("subject")
    if not subject_val:
        subject_val = payload_dict.get("applied_subject")
        
    dept_str = str(dept_val).strip() if dept_val and not pd.isna(dept_val) else ""
    subject_str = str(subject_val).strip() if subject_val and not pd.isna(subject_val) else ""
    
    # Resolve Mapped Department ID
    resolved_dept = resolve_candidate_department(dept_str, subject_str, depts)
    if resolved_dept["error"]:
        if resolved_dept["error"] == "Department mapping ambiguous":
            return {"candidate": None, "error": "Department mapping ambiguous", "app_id": app_id_str}
        else:
            return {"candidate": None, "error": "Department not found", "app_id": app_id_str}
            
    dept_id = resolved_dept["id"]
    mapped_dept = next((d for d in depts if d.id == dept_id), None)
    mapped_dept_name = mapped_dept.department_name if mapped_dept else ""
    
    # 5. Validate Email (if present)
    email_val = payload_dict.get("email")
    if not email_val:
        email_val = payload_dict.get("mail_id")
    clean_email = str(email_val).strip() if email_val and not pd.isna(email_val) else None
    
    if clean_email and not validate_email(clean_email):
        return {"candidate": None, "error": f"Invalid email format: '{clean_email}'.", "app_id": app_id_str}
        
    # 6. Validate Mobile (if present)
    mobile_val = payload_dict.get("mobile_number")
    clean_mobile = str(mobile_val).strip() if mobile_val and not pd.isna(mobile_val) else None
    
    if clean_mobile and not validate_mobile(clean_mobile):
        return {"candidate": None, "error": f"Invalid mobile number format: '{clean_mobile}'.", "app_id": app_id_str}
        
    # 7. Resolve Exam Session (if present)
    session_id = payload_dict.get("exam_session_id")
    session_val = payload_dict.get("exam_session")
    
    final_session_id = None
    if session_id is not None:
        final_session_id = int(session_id)
        session_exists = any(s.id == final_session_id and s.is_active for s in active_sessions)
        if not session_exists:
            return {"candidate": None, "error": "Specified exam session is inactive or does not exist.", "app_id": app_id_str}
    elif session_val and not pd.isna(session_val):
        session_str = str(session_val).strip().lower()
        for s in active_sessions:
            if s.session_name.strip().lower() == session_str:
                final_session_id = s.id
                break
                
    # 8. Photo mapping
    photo_info = find_candidate_photo(app_id_str)
    
    # 9. Populate Candidate Model
    candidate = Candidate(
        application_id=app_id_str,
        application_number=app_id_str,
        applicant_name=applicant_name_str,
        initial=initial_str if initial_str else None,
        name=name_str,
        dob=parsed_dob,
        category_ft_pt=str(payload_dict.get("category_ft_pt")).strip() if payload_dict.get("category_ft_pt") and not pd.isna(payload_dict.get("category_ft_pt")) else None,
        programme_offered=str(payload_dict.get("programme_offered")).strip() if payload_dict.get("programme_offered") and not pd.isna(payload_dict.get("programme_offered")) else None,
        subject=subject_str if subject_str else None,
        original_department_text=dept_str if dept_str else None,
        applied_subject=mapped_dept_name,
        email=clean_email,
        mobile_number=clean_mobile,
        department_id=dept_id,
        exam_session_id=final_session_id,
        photo_filename=photo_info["photo_filename"],
        photo_path=photo_info["photo_path"],
        photo_status=photo_info["photo_status"],
        is_active=True
    )
    
    return {"candidate": candidate, "error": None, "app_id": app_id_str}

@router.get("/", response_model=CandidateListResponse)
def get_candidates(
    search: Optional[str] = None,
    department_id: Optional[int] = None,
    photo_status: Optional[str] = None,
    category_ft_pt: Optional[str] = None,
    exam_session_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Retrieve a paginated list of candidates with search and filter parameters."""
    query = db.query(Candidate)

    # Search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.outerjoin(Department).filter(
            (Candidate.application_number.ilike(search_pattern)) |
            (Candidate.application_id.ilike(search_pattern)) |
            (Candidate.applicant_name.ilike(search_pattern)) |
            (Candidate.name.ilike(search_pattern)) |
            (Candidate.email.ilike(search_pattern)) |
            (Candidate.mobile_number.ilike(search_pattern)) |
            (Candidate.subject.ilike(search_pattern)) |
            (Candidate.original_department_text.ilike(search_pattern)) |
            (Department.department_name.ilike(search_pattern))
        )

    # Department filter
    if department_id is not None:
        query = query.filter(Candidate.department_id == department_id)

    # Photo status filter
    if photo_status:
        query = query.filter(Candidate.photo_status == photo_status)

    # Category filter
    if category_ft_pt:
        query = query.filter(Candidate.category_ft_pt == category_ft_pt)

    # Exam Session filter
    if exam_session_id is not None:
        query = query.filter(Candidate.exam_session_id == exam_session_id)

    total = query.count()
    pages = math.ceil(total / limit) if total > 0 else 1
    
    # Calculate offset
    offset = (page - 1) * limit
    candidates = query.order_by(Candidate.id.desc()).offset(offset).limit(limit).all()

    items = []
    for cand in candidates:
        dept_name = cand.department.department_name if cand.department else "Unknown"
        items.append(
            CandidateResponse(
                id=cand.id,
                application_number=cand.application_number,
                application_id=cand.application_id,
                applicant_name=cand.applicant_name,
                initial=cand.initial,
                category_ft_pt=cand.category_ft_pt,
                programme_offered=cand.programme_offered,
                subject=cand.subject,
                original_department_text=cand.original_department_text,
                name=cand.name,
                email=cand.email,
                dob=cand.dob,
                mobile_number=cand.mobile_number,
                applied_subject=cand.applied_subject,
                department_id=cand.department_id,
                department_name=dept_name,
                photo_filename=cand.photo_filename,
                photo_path=cand.photo_path,
                photo_status=cand.photo_status,
                is_active=cand.is_active,
                created_at=cand.created_at
            )
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate_by_id(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Retrieve detailed information of a single candidate by ID."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    dept_name = cand.department.department_name if cand.department else "Unknown"
    
    return CandidateResponse(
        id=cand.id,
        application_number=cand.application_number,
        application_id=cand.application_id,
        applicant_name=cand.applicant_name,
        initial=cand.initial,
        category_ft_pt=cand.category_ft_pt,
        programme_offered=cand.programme_offered,
        subject=cand.subject,
        original_department_text=cand.original_department_text,
        name=cand.name,
        email=cand.email,
        dob=cand.dob,
        mobile_number=cand.mobile_number,
        applied_subject=cand.applied_subject,
        department_id=cand.department_id,
        department_name=dept_name,
        photo_filename=cand.photo_filename,
        photo_path=cand.photo_path,
        photo_status=cand.photo_status,
        is_active=cand.is_active,
        created_at=cand.created_at
    )

@router.get("/template")
def download_candidate_template(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Generates and serves sample Candidate Upload Excel template."""
    from fastapi.responses import FileResponse
    template_path = os.path.join(EXCEL_DIR, "Candidate_Upload_Template.xlsx")

    sample_data = [
        {
            "Application ID": "CETPHD/J26/0128",
            "Applicant Name": "Gowtham",
            "Initial": "G",
            "Date of Birth": "06-01-2004",
            "Category (FT/PT)": "PT",
            "Mobile Number": "9344232463",
            "Email Address": "gowtham114411@gmail.com",
            "Department": "Computer Science",
            "Programme Offered": "Ph.D. Computer Science",
            "Subject": "Computer Science",
            "Exam Session": "Session 1"
        },
        {
            "Application ID": "CETPHD/J26/0129",
            "Applicant Name": "Sam",
            "Initial": "B",
            "Date of Birth": "22-08-1999",
            "Category (FT/PT)": "FT",
            "Mobile Number": "9876543211",
            "Email Address": "sam@gmail.com",
            "Department": "Mathematics",
            "Programme Offered": "Ph.D. Mathematics",
            "Subject": "Mathematics",
            "Exam Session": "Session 2"
        }
    ]
    df = pd.DataFrame(sample_data)
    df.to_excel(template_path, index=False)

    return FileResponse(
        template_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Candidate_Upload_Template.xlsx"
    )

@router.post("/upload-excel", response_model=CandidateUploadSummary)
def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Process batch candidate uploads from Excel sheets."""
    from app.config import MAX_UPLOAD_SIZE_MB
    from app.logging_config import log_error

    # Validate file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        log_error(f"Candidate Excel upload failed: File size {file_size} exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds size limit of {MAX_UPLOAD_SIZE_MB}MB."
        )

    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".xlsx", ".xls"]:
        log_error(f"Candidate Excel upload failed: Invalid file extension {ext}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only Excel files (.xlsx, .xls) are allowed."
        )

    # Save uploaded file
    file_uuid = str(uuid.uuid4())
    stored_filename = f"{file_uuid}{ext}"
    local_path = os.path.join(EXCEL_DIR, stored_filename)
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        xl = pd.ExcelFile(local_path)
        sheet_to_use = "Applications" if "Applications" in xl.sheet_names else xl.sheet_names[0]
        # Peek first 30 rows as lists to locate header row
        df_peek = pd.read_excel(local_path, sheet_name=sheet_to_use, nrows=30, header=None, keep_default_na=False)
        peek_lists = df_peek.values.tolist()
        
        header_idx = find_header_row(peek_lists)
        if header_idx == -1:
            header_idx = 0
            
        df = pd.read_excel(local_path, sheet_name=sheet_to_use, skiprows=header_idx, keep_default_na=False)
    except Exception as e:
        log_error(f"Candidate Excel upload failed: Failed to read Excel file error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read Excel file: {str(e)}"
        )

    # Normalize columns
    df.columns = [normalize_column_name(c) for c in df.columns]

    # Validate required keys
    required_keys = ["application_id", "applicant_name", "dob"]
    missing_keys = [k for k in required_keys if k not in df.columns]
    if ("department" not in df.columns) and ("subject" not in df.columns):
        missing_keys.append("department")
        
    if missing_keys:
        key_to_official = {
            "application_id": "Application ID",
            "applicant_name": "Applicant Name",
            "dob": "Date of Birth",
            "department": "Department"
        }
        missing_display = [key_to_official.get(k, k) for k in missing_keys]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required columns in Excel: {', '.join(missing_display)}"
        )

    # Load references
    departments = db.query(Department).all()
    from app.models.exam_session import ExamSession
    active_sessions = db.query(ExamSession).filter(ExamSession.is_active == True).all()

    # Track summary
    total_rows = len(df)
    success_count = 0
    failed_count = 0
    photo_available_count = 0
    photo_missing_count = 0
    duplicate_in_excel_count = 0
    duplicate_in_database_count = 0
    errors = []
    
    excel_duplicates_tracker = set()
    import_batch_id = str(uuid.uuid4())
    candidates_to_add = []

    for index, row in df.iterrows():
        row_num = index + header_idx + 2
        
        payload_dict = {
            "application_id": row.get("application_id"),
            "applicant_name": row.get("applicant_name"),
            "initial": row.get("initial"),
            "dob": row.get("dob"),
            "category_ft_pt": row.get("category_ft_pt"),
            "mobile_number": row.get("mobile_number"),
            "email": row.get("email"),
            "department": row.get("department"),
            "programme_offered": row.get("programme_offered"),
            "subject": row.get("subject"),
            "exam_session": row.get("exam_session")
        }
        
        res = process_candidate_payload(
            db=db,
            payload_dict=payload_dict,
            depts=departments,
            active_sessions=active_sessions,
            excel_duplicates_tracker=excel_duplicates_tracker,
            is_manual=False
        )
        
        app_id_str = res.get("app_id") or ""
        if res["error"]:
            failed_count += 1
            if res["error"] == "Duplicate Application ID.":
                if app_id_str in excel_duplicates_tracker:
                    duplicate_in_excel_count += 1
                    errors.append({
                        "row": row_num,
                        "application_id": app_id_str,
                        "error": "Duplicate application ID"
                    })
                else:
                    duplicate_in_database_count += 1
                    errors.append({
                        "row": row_num,
                        "application_id": app_id_str,
                        "error": "Duplicate application ID"
                    })
            else:
                errors.append({
                    "row": row_num,
                    "application_id": app_id_str or None,
                    "error": res["error"]
                })
            continue
            
        excel_duplicates_tracker.add(app_id_str)
        cand = res["candidate"]
        cand.import_batch_id = import_batch_id
        candidates_to_add.append(cand)
        success_count += 1
        
        if cand.photo_status == "available":
            photo_available_count += 1
        else:
            photo_missing_count += 1

    # Bulk insert valid records
    if candidates_to_add:
        db.add_all(candidates_to_add)

    # Save Import Log
    import_log = ImportLog(
        upload_type="candidate",
        file_name=file.filename,
        total_records=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        error_details=json.dumps(errors),
        uploaded_by=current_admin.id
    )
    db.add(import_log)
    db.commit()

    return {
        "message": "Candidate upload completed",
        "total_rows": total_rows,
        "success_count": success_count,
        "failed_count": failed_count,
        "photo_available_count": photo_available_count,
        "photo_missing_count": photo_missing_count,
        "duplicate_in_excel_count": duplicate_in_excel_count,
        "duplicate_in_database_count": duplicate_in_database_count,
        "errors": errors
    }

@router.post("/upload-photos")
def upload_photos(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Upload multiple image photos and map them to existing candidate entries."""
    from app.config import MAX_UPLOAD_SIZE_MB
    from app.logging_config import log_error

    allowed_extensions = [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]
    uploaded_count = 0
    mapped_count = 0

    # Validate file size limits for all files first
    for file in files:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)
        if file_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            log_error(f"Candidate photo upload failed: File {file.filename} exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded photo file {file.filename} exceeds size limit of {MAX_UPLOAD_SIZE_MB}MB."
            )

    # Retrieve mapping list of all candidates for fast lookups
    candidates = db.query(Candidate).all()
    # Create lookup based on expected base filename mapping
    filename_to_candidate = {}
    for c in candidates:
        filename_to_candidate[generate_photo_filename(c.application_number)] = c
        filename_to_candidate[generate_photo_filename(c.application_id)] = c

    for file in files:
        orig_filename = os.path.basename(file.filename)
        base_name, ext = os.path.splitext(orig_filename)
        if ext not in allowed_extensions:
            continue  # Skip unallowed formats

        # Keep original filename case, but get base target
        stored_filename = f"{base_name}{ext}"
        local_path = os.path.join(PHOTO_DIR, stored_filename)

        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        uploaded_count += 1

        # Check mapping matching
        matched_candidate = filename_to_candidate.get(base_name)
        if not matched_candidate:
            # Try alternate CETPHD vs CET-PHD prefix check
            alt_base = base_name
            if base_name.startswith("CETPHD-"):
                alt_base = "CET-PHD-" + base_name[7:]
            elif base_name.startswith("CET-PHD-"):
                alt_base = "CETPHD-" + base_name[8:]
            matched_candidate = filename_to_candidate.get(alt_base)

        if matched_candidate:
            matched_candidate.photo_filename = stored_filename
            matched_candidate.photo_path = f"/static/candidate_photos/{stored_filename}"
            matched_candidate.photo_status = "available"
            mapped_count += 1

    db.commit()
    
    unmapped_count = uploaded_count - mapped_count
    return {
        "message": "Photos uploaded and mapped successfully",
        "uploaded_count": uploaded_count,
        "mapped_count": mapped_count,
        "unmapped_count": unmapped_count
    }

@router.post("/remap-photos")
def remap_photos(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Scan candidate_photos folder and refresh status/paths of all candidate entries."""
    candidates = db.query(Candidate).all()
    updated_count = 0

    for cand in candidates:
        photo_info = find_candidate_photo(cand.application_id or cand.application_number)
        
        # Verify if changes are needed
        if (cand.photo_status != photo_info["photo_status"] or 
            cand.photo_filename != photo_info["photo_filename"] or 
            cand.photo_path != photo_info["photo_path"]):
            
            cand.photo_filename = photo_info["photo_filename"]
            cand.photo_path = photo_info["photo_path"]
            cand.photo_status = photo_info["photo_status"]
            updated_count += 1

    if updated_count > 0:
        db.commit()

    return {
        "message": f"Successfully rescanned candidate photos directory. Updated {updated_count} candidate records.",
        "updated_count": updated_count
    }

from pydantic import BaseModel

class CandidateBulkDeleteRequest(BaseModel):
    candidate_ids: List[int]

@router.post("/manual", status_code=status.HTTP_201_CREATED)
def manual_create_candidate(
    payload: CandidateManualCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Add candidate manually with strict validations and photo mapping checks."""
    import logging
    logger = logging.getLogger("phd_app")

    # Load departments and sessions
    departments = db.query(Department).all()
    from app.models.exam_session import ExamSession
    active_sessions = db.query(ExamSession).filter(ExamSession.is_active == True).all()

    # Convert Pydantic payload to dictionary
    payload_dict = payload.dict()
    
    excel_duplicates_tracker = set()
    
    res = process_candidate_payload(
        db=db,
        payload_dict=payload_dict,
        depts=departments,
        active_sessions=active_sessions,
        excel_duplicates_tracker=excel_duplicates_tracker,
        is_manual=True
    )
    
    if res["error"]:
        if res["error"] == "Duplicate Application ID.":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Application number already exists"
            )
        elif "Invalid Date of Birth" in res["error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Date of Birth. Must be in DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD format."
            )
        elif "Applied subject" in res["error"] or "Department not found" in res["error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Applied subject does not match any department"
            )
        elif "ambiguous" in res["error"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department mapping ambiguous"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=res["error"]
            )

    new_candidate = res["candidate"]
    try:
        db.add(new_candidate)
        db.commit()
        db.refresh(new_candidate)

        logger.info(f"Admin {current_admin.email} manually added candidate: {new_candidate.application_id}")

        return {
            "message": "Candidate added successfully",
            "candidate": {
                "id": new_candidate.id,
                "application_number": new_candidate.application_number,
                "name": new_candidate.name,
                "department_name": new_candidate.department.department_name if new_candidate.department else "",
                "photo_status": new_candidate.photo_status
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to manually add candidate {new_candidate.application_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while manually adding candidate: {str(e)}"
        )

@router.delete("/bulk-delete")
def bulk_delete_candidates(
    payload: CandidateBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Bulk delete candidates and their attempts/answers permanently."""
    if not payload.candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="candidate_ids list cannot be empty"
        )

    from app.models.exam_attempt import ExamAttempt
    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # Get attempts for these candidates
        attempt_ids = [a.id for a in db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(payload.candidate_ids)).all()]
        
        # 1. Delete CandidateAnswer rows linked to candidate attempts
        answers_deleted = 0
        if attempt_ids:
            answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)

        # 2. Delete ExamAttempt rows linked to candidate
        attempts_deleted = db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(payload.candidate_ids)).delete(synchronize_session=False)

        # 3. Delete Candidate rows
        candidates_deleted = db.query(Candidate).filter(Candidate.id.in_(payload.candidate_ids)).delete(synchronize_session=False)

        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently bulk-deleted candidate IDs: {payload.candidate_ids}")

        return {
            "message": "Candidates permanently deleted",
            "deleted_candidate_ids": payload.candidate_ids,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "exam_attempts": attempts_deleted,
                "candidates": candidates_deleted
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed bulk deleting candidates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while bulk deleting candidates: {str(e)}"
        )

@router.delete("/{candidate_id}")
def delete_single_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Delete a single candidate and their attempts/answers permanently."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with ID {candidate_id} not found"
        )

    from app.models.exam_attempt import ExamAttempt
    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # Get attempts for this candidate
        attempt_ids = [a.id for a in db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id == candidate_id).all()]

        # 1. Delete CandidateAnswer rows linked to candidate attempts
        answers_deleted = 0
        if attempt_ids:
            answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)

        # 2. Delete ExamAttempt rows linked to candidate
        attempts_deleted = db.query(ExamAttempt).filter(ExamAttempt.candidate_id == candidate_id).delete(synchronize_session=False)

        # 3. Delete Candidate row
        app_number = candidate.application_number
        db.query(Candidate).filter(Candidate.id == candidate_id).delete(synchronize_session=False)
        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently deleted candidate ID {candidate_id} (App Number: {app_number})")

        return {
            "message": "Candidate permanently deleted",
            "candidate_id": candidate_id,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "exam_attempts": attempts_deleted,
                "candidates": 1
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete candidate ID {candidate_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while permanently deleting candidate: {str(e)}"
        )
