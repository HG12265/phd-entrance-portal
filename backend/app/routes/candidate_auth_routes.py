from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date
from app.database import get_db
from app.models.candidate import Candidate
from app.schemas.candidate_auth_schema import CandidateLoginRequest, CandidateLoginResponse, CandidateProfileResponse
from app.utils.security import create_access_token
from app.utils.candidate_auth_dependency import get_current_candidate

from app.logging_config import log_exam_event

router = APIRouter()

def parse_dob(dob_str: str) -> date:
    """Accept DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, DD-Mon-YYYY, and various date formats."""
    s = dob_str.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d-%b-%Y", "%d-%B-%Y", "%b-%d-%Y", "%B-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError("Invalid date format")

@router.post("/login", response_model=CandidateLoginResponse)
def candidate_login(payload: CandidateLoginRequest, db: Session = Depends(get_db)):
    """Log in a candidate using Application Number and Date of Birth."""
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid application number or date of birth",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        req_dob = parse_dob(payload.dob)
    except ValueError:
        log_exam_event("CANDIDATE_LOGIN", None, None, "FAILED", f"app_num={payload.application_number} DOB_parse_error")
        raise generic_error

    candidate = db.query(Candidate).filter(
        (Candidate.application_number == payload.application_number) |
        (Candidate.application_id == payload.application_number)
    ).first()
    
    if not candidate:
        log_exam_event("CANDIDATE_LOGIN", None, None, "FAILED", f"app_num={payload.application_number} candidate_not_found")
        raise generic_error

    if not candidate.is_active:
        log_exam_event("CANDIDATE_LOGIN", candidate.id, None, "FAILED", f"app_num={payload.application_number} candidate_inactive")
        raise generic_error

    # Verify matching date of birth
    if candidate.dob != req_dob:
        log_exam_event("CANDIDATE_LOGIN", candidate.id, None, "FAILED", f"app_num={payload.application_number} DOB_mismatch")
        raise generic_error

    # Create Access Token
    token_data = {
        "sub": candidate.application_number,
        "candidate_id": candidate.id,
        "role": "candidate"
    }
    access_token = create_access_token(data=token_data)
    log_exam_event("CANDIDATE_LOGIN", candidate.id, None, "SUCCESS", f"app_num={candidate.application_number}")

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "candidate": {
            "id": candidate.id,
            "application_number": candidate.application_number,
            "name": candidate.name,
            "applied_subject": candidate.applied_subject,
            "department_id": candidate.department_id,
            "department_name": candidate.department.department_name if candidate.department else ""
        }
    }

@router.get("/me", response_model=CandidateProfileResponse)
def get_candidate_me(current_candidate: Candidate = Depends(get_current_candidate)):
    """Get the current candidate's profile details."""
    dob_str = ""
    if current_candidate.dob:
        if isinstance(current_candidate.dob, (date, datetime)):
            dob_str = current_candidate.dob.strftime('%Y-%m-%d')
        else:
            dob_str = str(current_candidate.dob)
            
    return {
        "id": current_candidate.id,
        "application_number": current_candidate.application_number,
        "application_id": current_candidate.application_id,
        "applicant_name": current_candidate.applicant_name,
        "initial": current_candidate.initial,
        "category_ft_pt": current_candidate.category_ft_pt,
        "programme_offered": current_candidate.programme_offered,
        "subject": current_candidate.subject,
        "original_department_text": current_candidate.original_department_text,
        "name": current_candidate.name,
        "email": current_candidate.email,
        "dob": dob_str,
        "mobile_number": current_candidate.mobile_number,
        "applied_subject": current_candidate.applied_subject,
        "department_id": current_candidate.department_id,
        "department_name": current_candidate.department.department_name if current_candidate.department else "",
        "photo_status": current_candidate.photo_status,
        "photo_url": current_candidate.photo_path
    }
