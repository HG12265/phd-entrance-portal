from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional
from app.database import get_db
from app.models.candidate import Candidate
from app.models.exam_session import ExamSession
from app.models.exam_attempt import ExamAttempt
from app.utils.candidate_auth_dependency import get_current_candidate
from app.utils.exam_lock_helper import check_device_lock

router = APIRouter()
kolkata_tz = ZoneInfo("Asia/Kolkata")

def get_candidate_session_and_status(candidate: Candidate, db: Session):
    """
    Resolves the candidate's exam session and computes timezone-aware status.
    """
    session = None
    server_now = datetime.now(kolkata_tz)
    
    # 1. Resolve session
    if candidate.exam_session_id is not None:
        session = db.query(ExamSession).filter(ExamSession.id == candidate.exam_session_id).first()
        if not session or not session.is_active:
            return None, {
                "server_time": server_now.isoformat(),
                "exam_session": None,
                "status": "no_session",
                "can_enter": False,
                "message": "Assigned exam session is not active"
            }
    else:
        active_sessions = db.query(ExamSession).filter(ExamSession.is_active == True).all()
        # Filter active sessions to only those that allow the candidate's department
        allowed_sessions = [
            s for s in active_sessions 
            if candidate.department_id in [dept.id for dept in s.departments]
        ]
        
        if len(allowed_sessions) == 0:
            return None, {
                "server_time": server_now.isoformat(),
                "exam_session": None,
                "status": "no_session",
                "can_enter": False,
                "message": "No active exam session scheduled for your department"
            }
        elif len(allowed_sessions) == 1:
            session = allowed_sessions[0]
        else:
            # Multiple active sessions, none explicitly assigned
            return None, {
                "server_time": server_now.isoformat(),
                "exam_session": None,
                "status": "no_session",
                "can_enter": False,
                "message": "Multiple active exam sessions found for your department"
            }

    # 2. Compare times using Asia/Kolkata timezone
    # Convert naive database datetimes into timezone-aware datetimes (Asia/Kolkata)
    start_aware = session.start_time.replace(tzinfo=kolkata_tz)
    end_aware = session.end_time.replace(tzinfo=kolkata_tz)

    session_data = {
        "id": session.id,
        "session_name": session.session_name,
        "exam_title": session.exam_title,
        "start_time": start_aware.isoformat(),
        "end_time": end_aware.isoformat(),
        "duration_minutes": session.duration_minutes
    }

    # Department restriction check
    allowed_dept_ids = [dept.id for dept in session.departments]
    if candidate.department_id not in allowed_dept_ids:
        return session, {
            "server_time": server_now.isoformat(),
            "exam_session": session_data,
            "status": "waiting",
            "can_enter": False,
            "message": "Exam is not active/scheduled for your department in this session."
        }

    if server_now < start_aware:
        return session, {
            "server_time": server_now.isoformat(),
            "exam_session": session_data,
            "status": "waiting",
            "can_enter": False,
            "message": "Exam has not started yet"
        }
    elif start_aware <= server_now <= end_aware:
        return session, {
            "server_time": server_now.isoformat(),
            "exam_session": session_data,
            "status": "live",
            "can_enter": True,
            "message": "Exam is live"
        }
    else:
        return session, {
            "server_time": server_now.isoformat(),
            "exam_session": session_data,
            "status": "ended",
            "can_enter": False,
            "message": "Exam has ended"
        }

@router.get("/exam-status")
def get_exam_status(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate)
):
    """Retrieve the candidate's exam session and checks current entry permissions."""
    session, status_data = get_candidate_session_and_status(current_candidate, db)
    if session:
        completed = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == current_candidate.id,
            ExamAttempt.exam_session_id == session.id,
            ExamAttempt.status.in_(["submitted", "auto_submitted"])
        ).order_by(
            ExamAttempt.submitted_time.is_(None).asc(),
            ExamAttempt.submitted_time.asc(),
            ExamAttempt.id.asc()
        ).first()
        if completed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Exam already completed",
                    "exam_completed": True,
                    "redirect_to_result": True,
                    "attempt_id": completed.id,
                    "can_enter": False
                }
            )
    return status_data

@router.get("/instructions")
def get_instructions(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate)
):
    """Retrieve details and active rules for instructions page."""
    session, status_data = get_candidate_session_and_status(current_candidate, db)
    
    # Default instructions
    default_rules = (
        "1. Total questions: 70\n"
        "2. Duration: 90 minutes\n"
        "3. Each question carries 1 mark\n"
        "4. No negative marks\n"
        "5. Minimum pass mark: 28\n"
        "6. Do not refresh or close the browser\n"
        "7. Submit before time ends\n"
        "8. Use only one device/browser"
    )

    instructions_text = default_rules
    session_name = "N/A"
    exam_title = "PhD Entrance Examination"
    start_time = "N/A"
    end_time = "N/A"
    duration = 90

    if session:
        session_name = session.session_name
        exam_title = session.exam_title
        start_time = session.start_time.replace(tzinfo=kolkata_tz).isoformat()
        end_time = session.end_time.replace(tzinfo=kolkata_tz).isoformat()
        duration = session.duration_minutes
        if session.instructions and session.instructions.strip():
            instructions_text = session.instructions.strip()

    res_data = {
        "candidate_name": current_candidate.name,
        "application_number": current_candidate.application_number,
        "department": current_candidate.department.department_name if current_candidate.department else "",
        "exam_title": exam_title,
        "session_name": session_name,
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
        "instructions": instructions_text
    }

    if session:
        completed = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == current_candidate.id,
            ExamAttempt.exam_session_id == session.id,
            ExamAttempt.status.in_(["submitted", "auto_submitted"])
        ).order_by(
            ExamAttempt.submitted_time.is_(None).asc(),
            ExamAttempt.submitted_time.asc(),
            ExamAttempt.id.asc()
        ).first()
        if completed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Exam already completed",
                    "exam_completed": True,
                    "redirect_to_result": True,
                    "attempt_id": completed.id,
                    "can_enter": False
                }
            )

    return res_data

@router.post("/exam/enter")
def enter_exam_room(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Verification guard for candidate entering the exam page.
    Only allows access if server time checks verify exam session is currently live.
    """
    session, status_data = get_candidate_session_and_status(current_candidate, db)
    
    if session:
        completed = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == current_candidate.id,
            ExamAttempt.exam_session_id == session.id,
            ExamAttempt.status.in_(["submitted", "auto_submitted"])
        ).order_by(
            ExamAttempt.submitted_time.is_(None).asc(),
            ExamAttempt.submitted_time.asc(),
            ExamAttempt.id.asc()
        ).first()
        if completed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Exam already completed",
                    "exam_completed": True,
                    "redirect_to_result": True,
                    "attempt_id": completed.id,
                    "can_enter": False
                }
            )

    if not status_data["can_enter"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=status_data.get("message", "Exam entry forbidden at this time.")
        )
        
    if session:
        check_device_lock(current_candidate, x_exam_client_id, db, session.id)
        
    return {
        "message": "Exam entry allowed",
        "next_step": "Phase 6 will start exam attempt"
    }
