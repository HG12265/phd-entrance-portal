from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.exam_session import ExamSession
from app.models.department import Department
from app.schemas.exam_session_schema import ExamSessionCreate, ExamSessionUpdate, ExamSessionResponse
from app.utils.auth_dependency import get_current_admin

router = APIRouter()

@router.get("/", response_model=List[ExamSessionResponse])
def list_exam_sessions(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """List all exam sessions ordered by start_time."""
    return db.query(ExamSession).order_by(ExamSession.start_time.asc()).all()

@router.get("/{session_id}", response_model=ExamSessionResponse)
def get_exam_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Get details of a specific exam session."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )
    return session

@router.post("/", response_model=ExamSessionResponse, status_code=status.HTTP_201_CREATED)
def create_exam_session(
    payload: ExamSessionCreate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Create a new exam session."""
    # Validation checks
    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )
    if payload.duration_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration must be a positive number of minutes"
        )

    # Check for active duplicate session names on the same exam date
    duplicate = db.query(ExamSession).filter(
        ExamSession.session_name == payload.session_name,
        ExamSession.exam_date == payload.exam_date,
        ExamSession.is_active == True
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active session named '{payload.session_name}' already exists for date {payload.exam_date}."
        )

    departments = []
    if payload.department_ids:
        departments = db.query(Department).filter(Department.id.in_(payload.department_ids)).all()

    new_session = ExamSession(
        session_name=payload.session_name,
        exam_title=payload.exam_title,
        exam_date=payload.exam_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        instructions=payload.instructions,
        is_active=True,
        departments=departments
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@router.put("/{session_id}", response_model=ExamSessionResponse)
def update_exam_session(
    session_id: int,
    payload: ExamSessionUpdate,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Update an exam session."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )

    # Validate times if both start_time and end_time are updated
    new_start = payload.start_time if payload.start_time is not None else session.start_time
    new_end = payload.end_time if payload.end_time is not None else session.end_time
    if new_start >= new_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )

    # Validate duration if updated
    if payload.duration_minutes is not None and payload.duration_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duration must be a positive number of minutes"
        )

    # Check for duplicate session name (ignoring self) if session_name or exam_date is modified
    new_name = payload.session_name if payload.session_name is not None else session.session_name
    new_date = payload.exam_date if payload.exam_date is not None else session.exam_date
    new_active = payload.is_active if payload.is_active is not None else session.is_active

    if new_active:
        duplicate = db.query(ExamSession).filter(
            ExamSession.session_name == new_name,
            ExamSession.exam_date == new_date,
            ExamSession.is_active == True,
            ExamSession.id != session_id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An active session named '{new_name}' already exists for date {new_date}."
            )

    # Apply updates
    update_data = payload.model_dump(exclude_unset=True)
    department_ids = update_data.pop("department_ids", None)

    for field, value in update_data.items():
        setattr(session, field, value)

    if department_ids is not None:
        departments = db.query(Department).filter(Department.id.in_(department_ids)).all()
        session.departments = departments

    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}")
def delete_exam_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Permanently delete an exam session with cascading cleanup and candidate unassignment."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found"
        )
    
    # Import models locally
    from app.models.candidate import Candidate
    from app.models.exam_attempt import ExamAttempt
    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # Get attempts for this session
        attempt_ids = [a.id for a in db.query(ExamAttempt.id).filter(ExamAttempt.exam_session_id == session_id).all()]
        
        # 1. Delete CandidateAnswer rows linked to attempts in session
        answers_deleted = 0
        if attempt_ids:
            answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)

        # 2. Delete ExamAttempt rows linked to session
        attempts_deleted = db.query(ExamAttempt).filter(ExamAttempt.exam_session_id == session_id).delete(synchronize_session=False)

        # 3. Set Candidate.exam_session_id = NULL for candidates mapped to session
        candidates_unassigned = db.query(Candidate).filter(Candidate.exam_session_id == session_id).update(
            {"exam_session_id": None}, synchronize_session=False
        )

        # 4. Delete the ExamSession row
        session_name = session.session_name
        db.query(ExamSession).filter(ExamSession.id == session_id).delete(synchronize_session=False)
        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently deleted exam session ID {session_id} (Name: {session_name})")

        return {
            "message": "Exam session permanently deleted",
            "session_id": session_id,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "exam_attempts": attempts_deleted,
                "candidates_unassigned": candidates_unassigned,
                "exam_sessions": 1
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete exam session ID {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while permanently deleting exam session: {str(e)}"
        )
