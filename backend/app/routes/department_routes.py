from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.department import Department
from app.schemas.department_schema import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.utils.auth_dependency import get_current_admin
from app.models.admin import AdminUser

router = APIRouter()

@router.get("/", response_model=List[DepartmentResponse])
def get_all_departments(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Retrieve all departments ordered by department_name."""
    departments = db.query(Department).order_by(Department.department_name).all()
    return departments

@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department_by_id(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Retrieve a single department by its ID."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found"
        )
    return department

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new department. Verifies uniqueness of name and code."""
    # Check if department_name exists
    existing_name = db.query(Department).filter(Department.department_name == payload.department_name).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department name must be unique"
        )
        
    # Check if department_code exists
    existing_code = db.query(Department).filter(Department.department_code == payload.department_code).first()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department code must be unique"
        )

    db_dept = Department(
        department_name=payload.department_name,
        department_code=payload.department_code,
        description=payload.description
    )
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept

@router.put("/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update department details. Validates unique constraints if code or name is updated."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found"
        )

    # Validate name uniqueness if it is changing
    if payload.department_name is not None and payload.department_name != department.department_name:
        existing_name = db.query(Department).filter(Department.department_name == payload.department_name).first()
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department name must be unique"
            )
        department.department_name = payload.department_name

    # Validate code uniqueness if it is changing
    if payload.department_code is not None and payload.department_code != department.department_code:
        existing_code = db.query(Department).filter(Department.department_code == payload.department_code).first()
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department code must be unique"
            )
        department.department_code = payload.department_code

    if payload.description is not None:
        department.description = payload.description

    if payload.is_active is not None:
        department.is_active = payload.is_active

    db.commit()
    db.refresh(department)
    return department

@router.delete("/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Permanently delete a department and all related records from DB with cascade safety."""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with ID {department_id} not found"
        )
        
    # Import models locally to avoid circular dependency
    from app.models.candidate import Candidate
    from app.models.question import Question
    from app.models.exam_attempt import ExamAttempt
    from app.models.candidate_answer import CandidateAnswer
    from sqlalchemy import or_
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # 1. Candidate IDs in department
        cand_ids = [c.id for c in db.query(Candidate.id).filter(Candidate.department_id == department_id).all()]
        
        # 2. Attempt IDs of candidates in department
        attempt_ids_cand = [a.id for a in db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(cand_ids)).all()] if cand_ids else []
        
        # 3. Question IDs in department
        question_ids = [q.id for q in db.query(Question.id).filter(Question.department_id == department_id).all()]

        # delete answers
        answers_deleted = 0
        if attempt_ids_cand or question_ids:
            answers_deleted = db.query(CandidateAnswer).filter(
                or_(
                    CandidateAnswer.attempt_id.in_(attempt_ids_cand) if attempt_ids_cand else False,
                    CandidateAnswer.question_id.in_(question_ids) if question_ids else False
                )
            ).delete(synchronize_session=False)

        # delete attempts
        attempts_deleted = db.query(ExamAttempt).filter(
            or_(
                ExamAttempt.candidate_id.in_(cand_ids) if cand_ids else False,
                ExamAttempt.department_id == department_id
            )
        ).delete(synchronize_session=False)

        # delete candidates
        candidates_deleted = db.query(Candidate).filter(Candidate.department_id == department_id).delete(synchronize_session=False)

        # delete questions
        questions_deleted = db.query(Question).filter(Question.department_id == department_id).delete(synchronize_session=False)

        # delete department
        dept_code = department.department_code
        db.query(Department).filter(Department.id == department_id).delete(synchronize_session=False)
        db.commit()

        # Log admin action
        logger.info(f"Admin {current_admin.email} permanently deleted department ID {department_id} (Code: {dept_code})")

        return {
            "message": "Department permanently deleted",
            "department_id": department_id,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "exam_attempts": attempts_deleted,
                "candidates": candidates_deleted,
                "questions": questions_deleted,
                "departments": 1
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete department ID {department_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while permanently deleting department: {str(e)}"
        )
