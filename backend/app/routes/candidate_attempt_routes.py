from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import secrets
import time
import random
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer
from app.utils.candidate_auth_dependency import get_current_candidate
from app.routes.candidate_exam_routes import get_candidate_session_and_status
from app.routes.candidate_submit_routes import finalize_attempt
from app.utils.exam_lock_helper import check_device_lock

router = APIRouter()
kolkata_tz = ZoneInfo("Asia/Kolkata")

# Pydantic Schemas for Requests
class SaveAnswerRequest(BaseModel):
    attempt_id: int
    question_id: int
    selected_option: Optional[str] = None
    answer_status: Optional[str] = None

class MarkStatusRequest(BaseModel):
    attempt_id: int
    question_id: int
    answer_status: str

def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "Unknown"

@router.post("/start")
def start_exam(
    request: Request,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Starts a candidate's exam attempt.
    Phase 17 fix: Always resumes existing in_progress attempt (including force-reopened ones).
    Never recreates CandidateAnswer rows if they already exist.
    """
    # Phase 17: Prevent race conditions by locking candidate row
    db.query(Candidate).filter(Candidate.id == current_candidate.id).with_for_update().first()
    
    server_now = datetime.now(kolkata_tz)

    # 1. Reuse session check logic from Phase 5
    session, session_status = get_candidate_session_and_status(current_candidate, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=session_status.get("message", "No active exam session found.")
        )

    # 2. Check for completed attempt first (submitted/auto_submitted)
    # Phase 17: Use with_for_update() to bypass repeatable-read snapshot isolation
    completed = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_session_id == session.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).with_for_update().first()
    
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

    # 3. Phase 17: Check for existing in_progress attempt BEFORE device lock check.
    #    If one exists (including force-reopened), ALWAYS resume it.
    #    Use with_for_update() to bypass repeatable-read snapshot isolation.
    existing_inprogress = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_session_id == session.id,
        ExamAttempt.status == "in_progress"
    ).with_for_update().first()

    if existing_inprogress:
        # Check if time is expired
        end_time_aware = existing_inprogress.end_time.replace(tzinfo=kolkata_tz)
        if server_now > end_time_aware or existing_inprogress.status == "expired":
            finalize_attempt(db, existing_inprogress, "auto", server_now)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Exam already submitted"
            )

        # Transfer device lock if needed (handle force-reopened attempts)
        if x_exam_client_id:
            if existing_inprogress.lock_status == "reopened" or existing_inprogress.active_lock_token is None:
                # Transfer lock to this device
                existing_inprogress.active_lock_token = x_exam_client_id
                existing_inprogress.lock_status = "locked"
                existing_inprogress.locked_at = server_now.replace(tzinfo=None)
                existing_inprogress.last_client_fingerprint = x_exam_client_id
                db.commit()
                db.refresh(existing_inprogress)
            elif existing_inprogress.active_lock_token != x_exam_client_id:
                # Locked to a different device
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail={
                        "message": "Exam is locked to another device. Please contact admin to reopen your exam.",
                        "requires_admin_reopen": True
                    }
                )

        # Phase 17: Ensure all 70 answer rows exist — create only missing ones, NEVER overwrite
        # Use with_for_update() to bypass repeatable-read snapshot isolation
        existing_answer_count = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == existing_inprogress.id
        ).with_for_update().count()

        if existing_answer_count < existing_inprogress.total_questions:
            try:
                shuffled_ids = json.loads(existing_inprogress.shuffled_question_order)
            except Exception:
                shuffled_ids = []

            if shuffled_ids:
                existing_q_ids = {
                    ans.question_id for ans in db.query(CandidateAnswer).filter(
                        CandidateAnswer.attempt_id == existing_inprogress.id
                    ).with_for_update().all()
                }
                missing_ids = [q_id for q_id in shuffled_ids if q_id not in existing_q_ids]
                if missing_ids:
                    new_answers = []
                    for q_id in missing_ids:
                        new_answers.append(CandidateAnswer(
                            attempt_id=existing_inprogress.id,
                            candidate_id=current_candidate.id,
                            question_id=q_id,
                            selected_option=None,
                            answer_status="not_visited"
                        ))
                    db.add_all(new_answers)
                    db.commit()

        return get_attempt_state_response(existing_inprogress, db, server_now)

    # 4. No in_progress attempt — validate device lock for completeness
    existing_attempt = check_device_lock(current_candidate, x_exam_client_id, db, session.id)
    if existing_attempt:
        end_time_aware = existing_attempt.end_time.replace(tzinfo=kolkata_tz)
        if server_now > end_time_aware or existing_attempt.status == "expired":
            finalize_attempt(db, existing_attempt, "auto", server_now)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Exam already submitted"
            )
        return get_attempt_state_response(existing_attempt, db, server_now)

    # 5. Create a fresh attempt (entry allowed check)
    if not session_status.get("can_enter"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=session_status.get("message", "Access denied at this time.")
        )

    if not current_candidate.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your profile is not assigned to any academic department."
        )

    # Validate active questions registry count
    active_q_count = db.query(Question).filter(
        Question.department_id == current_candidate.department_id,
        Question.is_active == True
    ).count()

    if active_q_count != 70:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exam questions for your subject are not ready (found {active_q_count} active questions instead of 70)."
        )

    # Fetch and shuffle question IDs
    questions = db.query(Question).filter(
        Question.department_id == current_candidate.department_id,
        Question.is_active == True
    ).all()
    
    q_ids = [q.id for q in questions]
    secrets.SystemRandom().shuffle(q_ids)

    duration = timedelta(minutes=session.duration_minutes)
    sess_end_aware = session.end_time.replace(tzinfo=kolkata_tz)
    calculated_end_time = min(server_now + duration, sess_end_aware)

    # Create attempt row and batch insert CandidateAnswer rows with deadlock retries
    max_retries = 5
    for attempt_retry in range(max_retries):
        try:
            # Re-lock candidate row after rollback if this is a retry
            if attempt_retry > 0:
                db.query(Candidate).filter(Candidate.id == current_candidate.id).with_for_update().first()
                
            new_attempt = ExamAttempt(
                candidate_id=current_candidate.id,
                department_id=current_candidate.department_id,
                exam_session_id=session.id,
                start_time=server_now,
                end_time=calculated_end_time,
                status="in_progress",
                total_questions=70,
                shuffled_question_order=json.dumps(q_ids),
                # Initialize Phase 11 Lock fields
                active_lock_token=x_exam_client_id,
                lock_status="locked",
                locked_at=server_now.replace(tzinfo=None),
                last_client_fingerprint=x_exam_client_id,
                # Phase 18 fields
                login_time=server_now.replace(tzinfo=None),
                system_ip=get_client_ip(request)
            )
            db.add(new_attempt)
            db.flush()

            # Batch insert CandidateAnswer rows starting with "not_visited"
            answers = []
            for q_id in q_ids:
                ans = CandidateAnswer(
                    attempt_id=new_attempt.id,
                    candidate_id=current_candidate.id,
                    question_id=q_id,
                    selected_option=None,
                    answer_status="not_visited"
                )
                answers.append(ans)
            
            db.bulk_save_objects(answers)
            db.commit()
            break
        except OperationalError as e:
            db.rollback()
            is_deadlock = False
            if e.orig and getattr(e.orig, 'args', None):
                if e.orig.args[0] == 1213:
                    is_deadlock = True
            
            if is_deadlock and attempt_retry < max_retries - 1:
                # Sleep a randomized backoff time and retry
                time.sleep(random.uniform(0.05, 0.25))
                continue
            else:
                raise

    from app.logging_config import log_exam_event
    log_exam_event("EXAM_START", new_attempt.candidate_id, new_attempt.id, "SUCCESS")

    return get_attempt_state_response(new_attempt, db, server_now)


@router.get("/current")
def get_current_attempt(
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Returns the candidate's active exam attempt if exists and is live.
    Used for restoring state after a browser refresh.
    Phase 17: Handles force-reopened attempts — always returns saved selected_option.
    """
    server_now = datetime.now(kolkata_tz)

    session, session_status = get_candidate_session_and_status(current_candidate, db)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=session_status.get("message", "No active exam session found.")
        )

    # Check for completed attempt first
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

    # Phase 17: Find in_progress attempt FIRST (before device lock check)
    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == current_candidate.id,
        ExamAttempt.exam_session_id == session.id,
        ExamAttempt.status == "in_progress"
    ).first()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active exam attempt found."
        )

    # Phase 17: Handle device lock — if force-reopened, transfer lock to new device
    if attempt.lock_status == "reopened" or attempt.active_lock_token is None:
        # Force-reopened attempt: transfer lock to current device
        if x_exam_client_id:
            attempt.active_lock_token = x_exam_client_id
            attempt.lock_status = "locked"
            attempt.locked_at = server_now.replace(tzinfo=None)
            attempt.last_client_fingerprint = x_exam_client_id
            db.commit()
            db.refresh(attempt)
        # If no client_id header, still allow viewing (will be locked on next save)
    elif x_exam_client_id and attempt.active_lock_token != x_exam_client_id:
        # Locked to a different device
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "Exam is locked to another device. Please contact admin to reopen your exam.",
                "requires_admin_reopen": True
            }
        )

    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    if server_now > end_time_aware or attempt.status == "expired":
        # Auto-finalize on expiration
        finalize_attempt(db, attempt, "auto", server_now)

        return {
            "attempt_id": attempt.id,
            "status": attempt.status,
            "redirect": "/candidate/result",
            "message": "Exam already submitted",
            "questions": []
        }

    return get_attempt_state_response(attempt, db, server_now)

@router.post("/save-answer")
def save_candidate_answer(
    payload: SaveAnswerRequest,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Updates the selected MCQ option and updates the answer status.
    Blocks if exam time has expired or status is not in_progress.
    """
    server_now = datetime.now(kolkata_tz)

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == payload.attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam attempt not found."
        )

    # Validate device lock
    check_device_lock(current_candidate, x_exam_client_id, db, attempt.exam_session_id)

    if attempt.candidate_id != current_candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this attempt."
        )

    # Block if already finalized
    if attempt.status in ("submitted", "auto_submitted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam already submitted"
        )

    # Time expiration guard -> auto-finalizes and locks
    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    if server_now > end_time_aware or attempt.status == "expired":
        finalize_attempt(db, attempt, "auto", server_now)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam already submitted"
        )

    if attempt.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Saving answers blocked. Attempt is in status: {attempt.status}."
        )

    # Shuffled order check
    try:
        shuffled_ids = json.loads(attempt.shuffled_question_order)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reading shuffled question bank indexes."
        )

    if payload.question_id not in shuffled_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question ID does not belong to this exam attempt."
        )

    # Validate option constraints
    opt = payload.selected_option
    if opt not in (None, "", "A", "B", "C", "D"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid option selected. Allowed values: A, B, C, D or null."
        )
    opt_value = opt if opt else None

    # Fetch current answer
    answer = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id,
        CandidateAnswer.question_id == payload.question_id
    ).first()

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate answer record missing."
        )

    # Resolve answer status based on updates
    new_status = payload.answer_status
    if not new_status:
        # Resolve status automatically based on whether an option is provided
        if opt_value:
            new_status = "answered"
        else:
            new_status = "not_answered"
    else:
        # Resolve marked statuses combinations
        if new_status == "marked_for_review":
            if opt_value:
                new_status = "answered_marked_for_review"
            else:
                new_status = "marked_for_review"
        elif new_status == "answered_marked_for_review":
            if not opt_value:
                new_status = "marked_for_review"
        elif new_status == "answered" and not opt_value:
            new_status = "not_answered"

    answer.selected_option = opt_value
    answer.answer_status = new_status
    answer.answered_at = server_now
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        from app.logging_config import log_exam_event
        log_exam_event("SAVE_ANSWER", attempt.candidate_id, attempt.id, "FAILED", f"q_id={payload.question_id} error={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save answer to database."
        )

    return {
        "message": "Answer saved",
        "question_id": payload.question_id,
        "selected_option": opt_value,
        "answer_status": new_status,
        "saved_at": server_now.isoformat()
    }

@router.post("/mark-status")
def mark_question_status(
    payload: MarkStatusRequest,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Updates the candidate answer status metadata without resetting the option values.
    Supports first-view status transition: 'not_visited' -> 'not_answered'.
    """
    server_now = datetime.now(kolkata_tz)

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == payload.attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam attempt not found."
        )

    # Validate device lock
    check_device_lock(current_candidate, x_exam_client_id, db, attempt.exam_session_id)

    if attempt.candidate_id != current_candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this attempt."
        )

    # Block if already finalized
    if attempt.status in ("submitted", "auto_submitted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam already submitted"
        )

    # Time expiration check -> auto-finalizes
    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    if server_now > end_time_aware or attempt.status == "expired":
        finalize_attempt(db, attempt, "auto", server_now)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam already submitted"
        )

    if attempt.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Modifying question states blocked. Exam is not in progress."
        )

    answer = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id,
        CandidateAnswer.question_id == payload.question_id
    ).first()

    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate answer record missing."
        )

    current_status = answer.answer_status
    target_status = payload.answer_status

    # First view logic: change 'not_visited' to 'not_answered', keep others intact
    if target_status == "not_answered":
        if current_status == "not_visited":
            answer.answer_status = "not_answered"
            db.commit()
    # Mark review flags
    elif target_status == "marked_for_review":
        if answer.selected_option:
            answer.answer_status = "answered_marked_for_review"
        else:
            answer.answer_status = "marked_for_review"
        db.commit()
    # Clear review flags, fall back to answered/not_answered
    elif target_status == "clear_review":
        if answer.selected_option:
            answer.answer_status = "answered"
        else:
            answer.answer_status = "not_answered"
        db.commit()
    else:
        # Standard status setter if valid
        if target_status in ("not_visited", "not_answered", "answered", "marked_for_review", "answered_marked_for_review"):
            answer.answer_status = target_status
            db.commit()

    return {
        "message": "Status updated",
        "question_id": payload.question_id,
        "selected_option": answer.selected_option,
        "answer_status": answer.answer_status
    }

@router.get("/timer/{attempt_id}")
def get_exam_timer(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_candidate: Candidate = Depends(get_current_candidate),
    x_exam_client_id: Optional[str] = Header(None)
):
    """
    Syncs the frontend clock countdown with the backend server timestamp.
    Safely commits 'expired' attempt status shifts.
    """
    server_now = datetime.now(kolkata_tz)

    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam attempt not found."
        )

    # Validate device lock
    check_device_lock(current_candidate, x_exam_client_id, db, attempt.exam_session_id)

    if attempt.candidate_id != current_candidate.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this attempt."
        )

    # Return 0 remaining seconds immediately if submitted/auto-submitted
    if attempt.status in ("submitted", "auto_submitted"):
        end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
        return {
            "server_time": server_now.isoformat(),
            "end_time": end_time_aware.isoformat(),
            "remaining_seconds": 0,
            "status": attempt.status
        }

    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    
    if server_now > end_time_aware or attempt.status == "expired":
        finalize_attempt(db, attempt, "auto", server_now)
        return {
            "server_time": server_now.isoformat(),
            "end_time": end_time_aware.isoformat(),
            "remaining_seconds": 0,
            "status": attempt.status
        }

    remaining = int((end_time_aware - server_now).total_seconds())
    return {
        "server_time": server_now.isoformat(),
        "end_time": end_time_aware.isoformat(),
        "remaining_seconds": remaining,
        "status": attempt.status
    }

# Helper to construct response payload
def get_attempt_state_response(attempt: ExamAttempt, db: Session, server_now: datetime):
    """Constructs exam attempt questions without disclosing correct answers."""
    try:
        shuffled_ids = json.loads(attempt.shuffled_question_order)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database corrupted: invalid shuffled order string format."
        )

    # Load all candidate answers for mapping
    answers = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt.id).all()
    answer_map = {ans.question_id: ans for ans in answers}

    # Load department questions mapped by ID
    questions = db.query(Question).filter(Question.id.in_(shuffled_ids)).all()
    question_map = {q.id: q for q in questions}

    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    remaining = max(0, int((end_time_aware - server_now).total_seconds()))

    response_questions = []
    for idx, q_id in enumerate(shuffled_ids):
        q = question_map.get(q_id)
        if not q:
            continue
        ans = answer_map.get(q_id)
        
        response_questions.append({
            "question_id": q.id,
            "display_no": idx + 1,
            "question_text": q.question_text,
            "question_tamil": getattr(q, "question_tamil", None),
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "formula": getattr(q, "formula", None),
            "marks": q.marks,
            "image_path": q.image_path,
            "answer_status": ans.answer_status if ans else "not_visited",
            "selected_option": ans.selected_option if ans else None
        })

    return {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "server_time": server_now.isoformat(),
        "start_time": attempt.start_time.replace(tzinfo=kolkata_tz).isoformat(),
        "end_time": end_time_aware.isoformat(),
        "remaining_seconds": remaining,
        "total_questions": attempt.total_questions,
        "questions": response_questions
    }

class FullscreenEventRequest(BaseModel):
    attempt_id: int
    event_type: str  # entered_fullscreen, exited_fullscreen, fullscreen_unsupported
    timestamp: str

@router.post("/fullscreen-event")
def log_fullscreen_event(
    payload: FullscreenEventRequest,
    current_candidate: Candidate = Depends(get_current_candidate)
):
    """
    Logs candidate fullscreen state changes for administrative audits.
    """
    import logging
    logger = logging.getLogger("phd_app")
    logger.info(
        f"Fullscreen Audit: candidate_id={current_candidate.id} "
        f"attempt_id={payload.attempt_id} event={payload.event_type} timestamp={payload.timestamp}"
    )
    return {"status": "event_logged"}
