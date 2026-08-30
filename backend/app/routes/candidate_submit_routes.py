from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from typing import Optional
import json

from app.database import get_db
from app.models.candidate import Candidate
from app.models.exam_attempt import ExamAttempt
from app.models.exam_session import ExamSession
from app.models.department import Department
from app.utils.candidate_auth_dependency import get_current_candidate
from app.routes.candidate_exam_routes import get_candidate_session_and_status
from app.services.scoring_service import calculate_attempt_score
from app.utils.exam_lock_helper import check_device_lock

router = APIRouter(prefix="/api/candidate/exam")
kolkata_tz = ZoneInfo("Asia/Kolkata")

# Pydantic Schemas for Requests
class SubmitExamRequest(BaseModel):
    attempt_id: int
    submission_type: str  # manual, auto

def finalize_attempt(db: Session, attempt: ExamAttempt, submission_type: str, server_now: datetime):
    """
    Idempotently scores and finalizes an exam attempt.
    Commits database transactions in a single query transaction.
    Phase 17: Saves answer snapshot before scoring so force-reopen can restore answers.
    """
    if attempt.status in ("submitted", "auto_submitted", "invalidated_duplicate"):
        return attempt

    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz) if attempt.end_time.tzinfo is None else attempt.end_time
    server_now_aware = server_now.replace(tzinfo=kolkata_tz) if server_now.tzinfo is None else server_now
    remaining_seconds = int((end_time_aware - server_now_aware).total_seconds())
    attempt.remaining_seconds_at_submit = max(0, remaining_seconds)

    # Phase 17: Capture answer snapshot before scoring
    from app.models.candidate_answer import CandidateAnswer
    answer_rows = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id
    ).all()
    snapshot = []
    selected_count = 0
    for ans in answer_rows:
        snapshot.append({
            "question_id": ans.question_id,
            "selected_option": ans.selected_option,
            "answer_status": ans.answer_status,
            "answered_at": ans.answered_at.isoformat() if ans.answered_at else None
        })
        if ans.selected_option:
            selected_count += 1
    attempt.last_answer_snapshot_json = json.dumps(snapshot)
    attempt.selected_count_at_submit = selected_count

    # Resolve status and submission types
    if submission_type == "manual":
        if server_now <= end_time_aware:
            attempt.status = "submitted"
            attempt.submission_type = "manual"
        else:
            # Force auto submission if manual submit arrived late
            attempt.status = "auto_submitted"
            attempt.submission_type = "auto"
    else:
        # Auto-submit requested or elapsed
        attempt.status = "auto_submitted"
        attempt.submission_type = "auto"

    attempt.submitted_time = server_now
    
    # Calculate score
    calculate_attempt_score(db, attempt)
    
    # Commit changes
    db.commit()
    db.refresh(attempt)

    from app.logging_config import log_exam_event
    event_type = "EXAM_SUBMIT" if attempt.status == "submitted" else "EXAM_AUTO_SUBMIT"
    log_exam_event(event_type, attempt.candidate_id, attempt.id, "SUCCESS", f"score={attempt.score} selected_count={selected_count}")

    return attempt

@router.post("/submit")
def submit_exam(
    payload: SubmitExamRequest,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Finalizes the candidate's exam attempt manually or automatically.
    """
    server_now = datetime.now(kolkata_tz)

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == payload.attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam attempt not found."
        )

    if attempt.candidate_id != current_candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this attempt."
        )

    # Return existing result summary if this specific attempt is already submitted/auto_submitted
    if attempt.status in ("submitted", "auto_submitted"):
        return {
            "message": "Exam submitted successfully",
            "attempt_id": attempt.id,
            "status": attempt.status,
            "submission_type": attempt.submission_type,
            "score": attempt.score,
            "total_marks": 70,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "result_status": "QUALIFIED" if attempt.result_status == "PASS" else "NOT QUALIFIED" if attempt.result_status == "FAIL" else attempt.result_status,
            "submitted_time": attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.submitted_time else None
        }

    # If another completed attempt already exists for same candidate + session
    completed_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_session_id == attempt.exam_session_id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"]),
        ExamAttempt.id != attempt.id
    ).first()

    if completed_attempt:
        # Mark duplicate in_progress attempt as invalidated_duplicate
        if attempt.status == "in_progress":
            attempt.status = "invalidated_duplicate"
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam already completed for this candidate"
        )

    # Validate device lock
    check_device_lock(current_candidate, x_exam_client_id, db, attempt.exam_session_id)

    # Process and return
    final_attempt = finalize_attempt(db, attempt, payload.submission_type, server_now)

    return {
        "message": "Exam submitted successfully",
        "attempt_id": final_attempt.id,
        "status": final_attempt.status,
        "submission_type": final_attempt.submission_type,
        "score": final_attempt.score,
        "total_marks": 70,
        "correct_count": final_attempt.correct_count,
        "wrong_count": final_attempt.wrong_count,
        "unanswered_count": final_attempt.unanswered_count,
        "result_status": "QUALIFIED" if final_attempt.result_status == "PASS" else "NOT QUALIFIED" if final_attempt.result_status == "FAIL" else final_attempt.result_status,
        "submitted_time": final_attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if final_attempt.submitted_time else None
    }

@router.get("/result")
def get_candidate_result(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate)
):
    """
    Returns the candidate's latest evaluation result summary safely
    (without exposing options, keys, or question list payloads).
    """
    session, session_status = get_candidate_session_and_status(current_candidate, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active exam session mapped to candidate."
        )

    # Retrieve candidate's official (earliest) completed attempt
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_session_id == session.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()

    if not attempt:
        # Check if there is an in-progress attempt that was reopened from a submitted state
        reopened = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == current_candidate.id,
            ExamAttempt.exam_session_id == session.id,
            ExamAttempt.status == "in_progress",
            ExamAttempt.reopened_from_submitted == True
        ).first()
        if reopened:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No final result available. Exam is currently reopened/in progress."
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not available yet"
        )

    # Load department name
    dept = db.query(Department).filter(Department.id == current_candidate.department_id).first()
    dept_name = dept.department_name if dept else "N/A"

    return {
        "candidate": {
            "name": current_candidate.name,
            "application_number": current_candidate.application_number,
            "department_name": dept_name
        },
        "exam": {
            "session_name": session.session_name,
            "exam_title": session.exam_title,
            "total_questions": 70,
            "total_marks": 70,
            "pass_mark": 28
        },
        "result": {
            "attempt_id": attempt.id,
            "score": attempt.score,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "result_status": "QUALIFIED" if attempt.result_status == "PASS" else "NOT QUALIFIED" if attempt.result_status == "FAIL" else attempt.result_status,
            "submitted_time": attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat(),
            "submission_type": attempt.submission_type
        }
    }
