from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.models.exam_attempt import ExamAttempt
from app.models.candidate import Candidate
from typing import Optional

def check_device_lock(candidate: Candidate, client_id: Optional[str], db: Session, session_id: int) -> Optional[ExamAttempt]:
    """
    Validates candidate device lock status.
    Raises HTTPException (403 or 423) if locked or completed.
    Returns the current ExamAttempt if valid, or None if no attempt exists yet.
    """
    # 1. Check for completed attempt first
    completed_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.exam_session_id == session_id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()

    if completed_attempt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Exam already completed",
                "exam_completed": True,
                "redirect_to_result": True,
                "attempt_id": completed_attempt.id,
                "can_enter": False
            }
        )

    # 2. Otherwise look for an in_progress attempt
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.exam_session_id == session_id,
        ExamAttempt.status == "in_progress"
    ).first()
    
    if not attempt:
        return None
        
    # 2. Check fingerprint
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "Exam client fingerprint missing. Access denied.",
                "requires_admin_reopen": True
            }
        )
        
    # 3. If fingerprint matches, resume normally
    if attempt.active_lock_token == client_id:
        return attempt
        
    # 4. If admin reopened, transfer lock to the new client
    if attempt.lock_status == "reopened":
        attempt.active_lock_token = client_id
        attempt.lock_status = "locked"
        attempt.locked_at = datetime.now()
        attempt.last_client_fingerprint = client_id
        db.commit()
        return attempt
        
    # 5. Otherwise, lock candidate out
    raise HTTPException(
        status_code=status.HTTP_423_LOCKED,
        detail={
            "message": "Exam is locked to another device. Please contact admin to reopen your exam.",
            "requires_admin_reopen": True
        }
    )
