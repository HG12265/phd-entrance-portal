from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import func

from app.database import get_db
from app.models.candidate import Candidate
from app.models.exam_attempt import ExamAttempt
from app.models.exam_session import ExamSession
from app.models.department import Department
from app.models.candidate_answer import CandidateAnswer
from app.models.exam_attempt_reopen_audit import ExamAttemptReopenAudit
from app.utils.auth_dependency import get_current_admin

router = APIRouter(prefix="/api/admin/exam-control", tags=["Admin Exam Control"])
kolkata_tz = ZoneInfo("Asia/Kolkata")

class ReopenRequest(BaseModel):
    application_number: str
    reason: Optional[str] = "Administrative Unlock"

class ForceReopenSubmittedRequest(BaseModel):
    application_number: str
    reason: Optional[str] = "Administrative Reopen"
    confirm_text: Optional[str] = "REOPEN"
    extra_minutes: Optional[int] = None

@router.get("/candidate/{application_number:path}")
def get_candidate_exam_status(
    application_number: str,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Looks up exam lock and stats detail for a candidate by application number or ID.
    """
    search_val = application_number.strip()
    candidate = db.query(Candidate).filter(
        (func.lower(Candidate.application_number) == func.lower(search_val)) |
        (func.lower(Candidate.application_id) == func.lower(search_val))
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
        
    # Look for completed attempt first
    completed_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()

    attempt = completed_attempt or db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id
    ).order_by(ExamAttempt.id.desc()).first()
    
    dept = db.query(Department).filter(Department.id == candidate.department_id).first()
    dept_name = dept.department_name if dept else "N/A"
    
    if not attempt:
        return {
            "candidate": {
                "name": candidate.name,
                "application_number": candidate.application_number,
                "department_name": dept_name
            },
            "attempt": None,
            "can_reopen": False,
            "reason": "No active attempt exists. Candidate can log in and start the exam from any browser."
        }

    # Calculate answered/unanswered counts
    answers = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt.id).all()
    answered_count = sum(1 for a in answers if a.answer_status in ("answered", "answered_marked_for_review"))
    marked_count = sum(1 for a in answers if a.answer_status in ("marked_for_review", "answered_marked_for_review"))
    unanswered_count = sum(1 for a in answers if a.answer_status in ("not_visited", "not_answered"))

    server_now = datetime.now(kolkata_tz)
    
    if attempt.status in ("submitted", "auto_submitted"):
        if attempt.remaining_seconds_at_submit is not None:
            remaining_seconds = attempt.remaining_seconds_at_submit
        elif attempt.submitted_time is not None:
            sub_time_aware = attempt.submitted_time.replace(tzinfo=kolkata_tz) if attempt.submitted_time.tzinfo is None else attempt.submitted_time
            end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz) if attempt.end_time.tzinfo is None else attempt.end_time
            remaining_seconds = max(0, int((end_time_aware - sub_time_aware).total_seconds()))
        else:
            remaining_seconds = 0
    else:
        end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz) if attempt.end_time.tzinfo is None else attempt.end_time
        remaining_seconds = max(0, int((end_time_aware - server_now).total_seconds()))

    can_reopen = True
    reason = ""

    if attempt.status in ("submitted", "auto_submitted"):
        can_reopen = False
        reason = "Exam already completed"
    elif remaining_seconds <= 0 or attempt.status == "expired":
        can_reopen = False
        reason = "Exam time is over"
    elif attempt.lock_status == "reopened":
        can_reopen = False
        reason = "Exam is already reopened/unlocked"

    return {
        "candidate": {
            "name": candidate.name,
            "application_number": candidate.application_number,
            "department_name": dept_name
        },
        "attempt": {
            "id": attempt.id,
            "status": attempt.status,
            "lock_status": attempt.lock_status,
            "reopen_count": attempt.reopen_count,
            "answered_count": answered_count,
            "not_answered_count": unanswered_count,
            "marked_for_review_count": marked_count,
            "remaining_seconds": remaining_seconds
        },
        "can_reopen": can_reopen,
        "reason": reason
    }

@router.post("/reopen")
def reopen_candidate_exam(
    payload: ReopenRequest,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Overrides candidate device lock, enabling login and attempt resumption from another client.
    """
    search_val = payload.application_number.strip()
    candidate = db.query(Candidate).filter(
        (func.lower(Candidate.application_number) == func.lower(search_val)) |
        (func.lower(Candidate.application_id) == func.lower(search_val))
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    # Look for completed attempt first
    completed_attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()

    attempt = completed_attempt or db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id
    ).order_by(ExamAttempt.id.desc()).first()
    
    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active attempt found"
        )

    # 1. If status is submitted/auto_submitted, reject
    if attempt.status in ("submitted", "auto_submitted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam already completed and cannot be reopened."
        )

    # 2. If time is over, reject
    server_now = datetime.now(kolkata_tz)
    end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz)
    remaining_seconds = int((end_time_aware - server_now).total_seconds())

    if remaining_seconds <= 0 or attempt.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam time is over and cannot be reopened."
        )

    # 3. Apply Reopen parameters and log audit
    audit = ExamAttemptReopenAudit(
        attempt_id=attempt.id,
        candidate_id=candidate.id,
        admin_id=current_admin.id,
        reopen_type="device_unlock",
        old_status=attempt.status,
        new_status=attempt.status,
        old_end_time=attempt.end_time,
        new_end_time=attempt.end_time,
        remaining_seconds_granted=remaining_seconds,
        reason=payload.reason or "Administrative Unlock",
        old_submitted_time=attempt.submitted_time,
        old_score=attempt.score,
        old_result_status=attempt.result_status
    )
    db.add(audit)

    attempt.lock_status = "reopened"
    attempt.active_lock_token = None
    attempt.reopened_at = server_now.replace(tzinfo=None)
    attempt.reopened_by_admin_id = current_admin.id
    attempt.reopen_reason = payload.reason
    attempt.reopen_count += 1
    
    db.commit()
    db.refresh(attempt)

    import logging
    logger = logging.getLogger("phd_app")
    logger.info(
        f"Admin {current_admin.email} reopened candidate ID {candidate.id} "
        f"(App No: {candidate.application_number}) attempt ID {attempt.id} reason: {payload.reason}"
    )

    return {
        "message": "Candidate exam reopened successfully",
        "application_number": candidate.application_number,
        "attempt_id": attempt.id,
        "reopen_count": attempt.reopen_count,
        "remaining_seconds": remaining_seconds
    }

@router.post("/force-reopen-submitted")
def force_reopen_submitted(
    payload: ForceReopenSubmittedRequest,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Force reopens a completed (submitted/auto_submitted) exam attempt back to in_progress.
    Phase 17: Verifies answer preservation before and after reopen. Restores from snapshot if needed.
    """
    import json as _json
    import logging
    logger = logging.getLogger("phd_app")

    reason = (payload.reason or "").strip()
    if not reason:
        reason = "Administrative Reopen"

    confirm_text = (payload.confirm_text or "").strip().upper()
    if not confirm_text:
        confirm_text = "REOPEN"

    search_val = payload.application_number.strip()
    candidate = db.query(Candidate).filter(
        (func.lower(Candidate.application_number) == func.lower(search_val)) |
        (func.lower(Candidate.application_id) == func.lower(search_val))
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate does not have a submitted or auto-submitted attempt."
        )

    # 1. Determine remaining_seconds
    if attempt.remaining_seconds_at_submit is not None:
        remaining_seconds = attempt.remaining_seconds_at_submit
    elif attempt.submitted_time is not None:
        sub_time_aware = attempt.submitted_time.replace(tzinfo=kolkata_tz) if attempt.submitted_time.tzinfo is None else attempt.submitted_time
        end_time_aware = attempt.end_time.replace(tzinfo=kolkata_tz) if attempt.end_time.tzinfo is None else attempt.end_time
        remaining_seconds = max(0, int((end_time_aware - sub_time_aware).total_seconds()))
    else:
        remaining_seconds = 0

    if remaining_seconds <= 0:
        if not payload.extra_minutes or payload.extra_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No remaining time available. Provide extra minutes to reopen."
            )
        remaining_seconds = payload.extra_minutes * 60
    else:
        if payload.extra_minutes is not None and payload.extra_minutes > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Extra minutes can be used only when no remaining time is available."
            )

    # 2. Phase 17: Count selected answers BEFORE reopen
    selected_count_before = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id,
        CandidateAnswer.selected_option.isnot(None),
        CandidateAnswer.selected_option != ""
    ).count()
    answer_rows_before = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id
    ).count()

    logger.info(
        f"ForceReopen Phase17: attempt_id={attempt.id} candidate_id={candidate.id} "
        f"selected_before={selected_count_before} rows_before={answer_rows_before}"
    )

    # 3. Record audit log
    server_now = datetime.now(kolkata_tz)
    old_status = attempt.status
    old_end_time = attempt.end_time
    old_submitted_time = attempt.submitted_time
    old_score = attempt.score
    old_result_status = attempt.result_status

    audit = ExamAttemptReopenAudit(
        attempt_id=attempt.id,
        candidate_id=candidate.id,
        admin_id=current_admin.id,
        reopen_type="submitted_force_reopen",
        old_status=old_status,
        new_status="in_progress",
        old_end_time=old_end_time,
        new_end_time=server_now.replace(tzinfo=None) + timedelta(seconds=remaining_seconds),
        remaining_seconds_granted=remaining_seconds,
        reason=reason,
        old_submitted_time=old_submitted_time,
        old_score=old_score,
        old_result_status=old_result_status
    )
    db.add(audit)

    # 4. Clear ONLY scoring fields from CandidateAnswer rows.
    #    NEVER touch selected_option, answer_status, answered_at.
    db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt.id).update({
        CandidateAnswer.is_correct: None,
        CandidateAnswer.mark_awarded: 0
    }, synchronize_session=False)

    # 5. Reopen attempt — clear scoring fields, set status to in_progress
    attempt.status = "in_progress"
    attempt.end_time = server_now.replace(tzinfo=None) + timedelta(seconds=remaining_seconds)
    attempt.submitted_time = None
    attempt.submission_type = None
    if hasattr(attempt, 'evaluated_at'):
        attempt.evaluated_at = None
    attempt.result_status = None
    attempt.score = 0
    attempt.correct_count = 0
    attempt.wrong_count = 0
    attempt.unanswered_count = 0
    attempt.lock_status = "reopened"
    attempt.active_lock_token = None
    attempt.reopened_at = server_now.replace(tzinfo=None)
    attempt.reopened_by_admin_id = current_admin.id
    attempt.reopen_reason = reason
    attempt.reopen_count += 1
    attempt.submitted_reopen_count += 1
    attempt.submitted_reopened_at = server_now.replace(tzinfo=None)
    attempt.submitted_reopened_by_admin_id = current_admin.id
    attempt.submitted_reopen_reason = reason
    attempt.reopened_from_submitted = True

    db.commit()
    db.refresh(attempt)

    # 6. Phase 17: Count selected answers AFTER reopen — must equal before
    selected_count_after = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id,
        CandidateAnswer.selected_option.isnot(None),
        CandidateAnswer.selected_option != ""
    ).count()
    answer_rows_after = db.query(CandidateAnswer).filter(
        CandidateAnswer.attempt_id == attempt.id
    ).count()

    restored_from_snapshot = False

    # 7. Phase 17: If answers lost, restore from snapshot
    if selected_count_after < selected_count_before:
        logger.warning(
            f"ForceReopen Phase17 ANSWER LOSS DETECTED: attempt_id={attempt.id} "
            f"selected_before={selected_count_before} selected_after={selected_count_after}. "
            f"Attempting snapshot restore."
        )
        snapshot_json = attempt.last_answer_snapshot_json
        if snapshot_json:
            try:
                snapshot = _json.loads(snapshot_json)
                for snap_item in snapshot:
                    if snap_item.get("selected_option"):
                        db.query(CandidateAnswer).filter(
                            CandidateAnswer.attempt_id == attempt.id,
                            CandidateAnswer.question_id == snap_item["question_id"]
                        ).update({
                            CandidateAnswer.selected_option: snap_item["selected_option"],
                            CandidateAnswer.answer_status: snap_item.get("answer_status", "answered")
                        }, synchronize_session=False)
                db.commit()
                restored_from_snapshot = True

                # Re-count after restore
                selected_count_after = db.query(CandidateAnswer).filter(
                    CandidateAnswer.attempt_id == attempt.id,
                    CandidateAnswer.selected_option.isnot(None),
                    CandidateAnswer.selected_option != ""
                ).count()
                logger.info(
                    f"ForceReopen Phase17 snapshot restore done: attempt_id={attempt.id} "
                    f"selected_after_restore={selected_count_after}"
                )
            except Exception as restore_err:
                logger.error(f"ForceReopen Phase17 snapshot restore FAILED: {restore_err}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Force reopen failed because saved answers were not preserved and snapshot restore failed."
                )
        else:
            # No snapshot available — this is a fatal error for 1st ever reopen if answers missing
            logger.error(
                f"ForceReopen Phase17: answer loss with NO snapshot: attempt_id={attempt.id} "
                f"before={selected_count_before} after={selected_count_after}"
            )
            if selected_count_after < selected_count_before:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Force reopen failed because saved answers were not preserved."
                )

    logger.info(
        f"Admin {current_admin.email} force-reopened candidate ID {candidate.id} "
        f"attempt ID {attempt.id} with {remaining_seconds} remaining seconds. "
        f"selected_before={selected_count_before} selected_after={selected_count_after} "
        f"restored_from_snapshot={restored_from_snapshot}"
    )

    return {
        "message": "Submitted attempt reopened successfully",
        "attempt_id": attempt.id,
        "application_number": candidate.application_number,
        "remaining_seconds": remaining_seconds,
        "submitted_reopen_count": attempt.submitted_reopen_count,
        # Phase 17 debug fields
        "selected_answers_preserved": selected_count_after,
        "answer_rows": answer_rows_after,
        "selected_count_before": selected_count_before,
        "selected_count_after": selected_count_after,
        "answer_rows_before": answer_rows_before,
        "answer_rows_after": answer_rows_after,
        "restored_from_snapshot": restored_from_snapshot
    }


class AddExtraTimeRequest(BaseModel):
    application_number: str
    extra_minutes: int
    reason: str


@router.post("/add-extra-time")
def add_extra_time(
    payload: AddExtraTimeRequest,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Adds extra minutes to an in-progress or expired exam attempt.
    """
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required."
        )

    if payload.extra_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extra minutes must be greater than zero."
        )

    search_val = payload.application_number.strip()
    candidate = db.query(Candidate).filter(
        (func.lower(Candidate.application_number) == func.lower(search_val)) |
        (func.lower(Candidate.application_id) == func.lower(search_val))
    ).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )

    attempt = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == candidate.id,
        ExamAttempt.status.in_(["in_progress", "expired"])
    ).order_by(ExamAttempt.id.desc()).first()

    if not attempt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active (in-progress or expired) exam attempt found for this candidate."
        )

    server_now = datetime.now(kolkata_tz)
    old_end_time = attempt.end_time
    
    # Calculate new end_time: if current end_time is in the future, extend it.
    # If current end_time is in the past, set it to now + extra_minutes.
    old_end_time_aware = old_end_time.replace(tzinfo=kolkata_tz) if old_end_time.tzinfo is None else old_end_time
    if old_end_time_aware > server_now:
        new_end_time_aware = old_end_time_aware + timedelta(minutes=payload.extra_minutes)
    else:
        new_end_time_aware = server_now + timedelta(minutes=payload.extra_minutes)

    new_end_time = new_end_time_aware.replace(tzinfo=None)
    
    # Update attempt
    attempt.end_time = new_end_time
    attempt.status = "in_progress"  # Ensure it is in_progress so they can resume
    attempt.lock_status = "reopened"  # Automatically reopen device access too, as they had a problem!
    attempt.active_lock_token = None
    attempt.reopened_at = server_now.replace(tzinfo=None)
    attempt.reopened_by_admin_id = current_admin.id
    attempt.reopen_reason = f"Extra time added: {reason}"
    attempt.reopen_count += 1

    # Audit log
    audit = ExamAttemptReopenAudit(
        attempt_id=attempt.id,
        candidate_id=candidate.id,
        admin_id=current_admin.id,
        reopen_type="extra_time",
        old_status="in_progress",
        new_status="in_progress",
        old_end_time=old_end_time,
        new_end_time=new_end_time,
        remaining_seconds_granted=payload.extra_minutes * 60,
        reason=reason
    )
    db.add(audit)
    db.commit()
    db.refresh(attempt)

    import logging
    logger = logging.getLogger("phd_app")
    logger.info(
        f"Admin {current_admin.email} added {payload.extra_minutes} extra minutes to "
        f"candidate ID {candidate.id} (App No: {candidate.application_number}) attempt ID {attempt.id} reason: {reason}"
    )

    return {
        "message": f"Successfully added {payload.extra_minutes} minutes to the candidate's exam.",
        "application_number": candidate.application_number,
        "attempt_id": attempt.id,
        "new_end_time": new_end_time.isoformat()
    }

