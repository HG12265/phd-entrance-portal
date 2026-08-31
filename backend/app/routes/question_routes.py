import os
import uuid
import datetime
import pandas as pd
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.models import AdminUser, Department, Question, ImportLog
from app.utils.auth_dependency import get_current_admin
from app.schemas.question_schema import (
    QuestionResponse,
    QuestionUploadSummary,
    QuestionListResponse,
    DepartmentQuestionSummary,
    DashboardQuestionSummary
)
from app.utils.question_excel_utils import (
    COLUMN_MAPPING,
    normalize_question_column_name,
    validate_question_required_columns,
    parse_correct_option,
    parse_marks,
    clean_question_text,
    validate_question_row,
    detect_duplicate_question_numbers
)

router = APIRouter()

# Ensure uploads folder exists
UPLOAD_DIR = os.path.join("uploads", "question_excels")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("", response_model=QuestionListResponse)
def list_questions(
    department_id: Optional[int] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can view questions.")
    query = db.query(Question)
    
    if department_id is not None:
        query = query.filter(Question.department_id == department_id)
        
    if is_active is not None:
        query = query.filter(Question.is_active == is_active)
        
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Question.question_text.like(search_term),
                Question.option_a.like(search_term),
                Question.option_b.like(search_term),
                Question.option_c.like(search_term),
                Question.option_d.like(search_term)
            )
        )
        
    total = query.count()
    pages = (total + limit - 1) // limit if total > 0 else 1
    offset = (page - 1) * limit
    
    questions = query.order_by(Question.question_no.asc()).offset(offset).limit(limit).all()
    
    # Map department names
    items = []
    for q in questions:
        dept = db.query(Department).filter(Department.id == q.department_id).first()
        dept_name = dept.department_name if dept else None
        
        items.append(QuestionResponse(
            id=q.id,
            department_id=q.department_id,
            department_name=dept_name,
            question_no=q.question_no,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_option=q.correct_option,
            marks=q.marks,
            is_active=q.is_active,
            image_path=q.image_path,
            created_at=q.created_at
        ))
        
    return QuestionListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


@router.get("/summary/all", response_model=DashboardQuestionSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    # Fetch active departments
    active_depts = db.query(Department).filter(Department.is_active == True).all()
    
    ready_count = 0
    pending_count = 0
    total_active_questions = 0
    
    for dept in active_depts:
        active_q_count = db.query(Question).filter(
            and_(Question.department_id == dept.id, Question.is_active == True)
        ).count()
        
        total_active_questions += active_q_count
        if active_q_count == 70:
            ready_count += 1
        else:
            pending_count += 1
            
    return DashboardQuestionSummary(
        total_departments=len(active_depts),
        ready_departments=ready_count,
        pending_departments=pending_count,
        total_active_questions=total_active_questions
    )


@router.get("/template")
def download_question_template(
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can download the template.")
    template_path = os.path.join(UPLOAD_DIR, "question_template.xlsx")
    
    # Generate the template dynamically if not already exists
    if not os.path.exists(template_path):
        data = {
            "Question No": [1, 2],
            "Question Text": ["கணினியின் மூளை எது? / What is the brain of a computer?", "Integrate: ∫ x² dx"],
            "Option A": ["மின்னஞ்சல் / Email", "x³/3 + C"],
            "Option B": ["மத்திய கட்டுப்பாட்டு பகுதி / CPU", "x²/2 + C"],
            "Option C": ["வலைப்பின்னல் / Network", "2x + C"],
            "Option D": ["தரவு / Data", "x + C"],
            "Correct Option": ["B", "A"],
            "Marks": [1, 1]
        }
        df = pd.DataFrame(data)
        df.to_excel(template_path, index=False)
        
    return FileResponse(
        template_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Question_Upload_Template.xlsx"
    )


@router.get("/department/{department_id}/summary", response_model=DepartmentQuestionSummary)
def get_department_summary(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can view department summary.")
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
        
    active_count = db.query(Question).filter(
        and_(Question.department_id == department_id, Question.is_active == True)
    ).count()
    
    inactive_count = db.query(Question).filter(
        and_(Question.department_id == department_id, Question.is_active == False)
    ).count()
    
    # Find last upload details
    last_log = db.query(ImportLog).filter(
        and_(
            ImportLog.upload_type == "question_bank",
            ImportLog.error_details.like(f'%"department_id": {department_id}%')
        )
    ).order_by(ImportLog.id.desc()).first()
    
    last_batch_id = None
    last_uploaded = None
    
    # Try finding the batch ID from the latest question
    latest_q = db.query(Question).filter(
        Question.department_id == department_id
    ).order_by(Question.created_at.desc()).first()
    
    if latest_q:
        last_batch_id = latest_q.import_batch_id
        last_uploaded = latest_q.created_at
        
    return DepartmentQuestionSummary(
        department_id=department_id,
        department_name=dept.department_name,
        active_questions=active_count,
        inactive_questions=inactive_count,
        is_ready=(active_count == 70),
        last_uploaded_at=last_uploaded,
        last_import_batch_id=last_batch_id
    )


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can view questions.")
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
        
    dept = db.query(Department).filter(Department.id == q.department_id).first()
    dept_name = dept.department_name if dept else None
    
    return QuestionResponse(
        id=q.id,
        department_id=q.department_id,
        department_name=dept_name,
        question_no=q.question_no,
        question_text=q.question_text,
        option_a=q.option_a,
        option_b=q.option_b,
        option_c=q.option_c,
        option_d=q.option_d,
        correct_option=q.correct_option,
        marks=q.marks,
        is_active=q.is_active,
        image_path=q.image_path,
        created_at=q.created_at
    )


@router.post("/upload-excel/{department_id}", response_model=QuestionUploadSummary)
def upload_questions(
    department_id: int,
    replace_existing: bool = Query(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """
    Upload a question bank Excel file for a department.

    Supports:
    - Plain text questions (backward compatible)
    - LaTeX/Unicode math equations (MathJax rendering)
    - PNG / JPEG images embedded in Excel
    - EMF / WMF vector images (converted to PNG via ImageMagick)
    - OLE embedded objects (MathType / Equation Editor preview extraction)
    - OMML Office Math → LaTeX conversion
    - Mixed text + image + equation questions
    - Images inside answer options (A/B/C/D)
    """
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can upload question banks.")

    from app.config import MAX_UPLOAD_SIZE_MB
    from app.logging_config import log_error, log_info
    from app.services.excel_import.import_pipeline import run_advanced_import

    # 1. Validate department
    dept = db.query(Department).filter(
        and_(Department.id == department_id, Department.is_active == True)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Active department not found.")

    # 2. Check existing questions
    active_questions_count = db.query(Question).filter(
        and_(Question.department_id == department_id, Question.is_active == True)
    ).count()

    if active_questions_count > 0 and not replace_existing:
        raise HTTPException(
            status_code=400,
            detail="This department already has active questions. Use replace_existing=true to replace the question bank."
        )

    # 3. Validate file size and extension
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        log_error(f"Question Excel upload failed: File size {file_size} exceeds {MAX_UPLOAD_SIZE_MB}MB limit")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds size limit of {MAX_UPLOAD_SIZE_MB}MB."
        )

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".xlsx", ".xls"]:
        log_error(f"Question Excel upload failed: Invalid file extension {file_ext}")
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are allowed.")

    # 4. Save uploaded file
    batch_id = str(uuid.uuid4())
    stored_filename = f"{batch_id}{file_ext}"
    stored_path = os.path.join(UPLOAD_DIR, stored_filename)

    try:
        with open(stored_path, "wb") as f:
            f.write(file.file.read())
    except Exception as e:
        log_error(f"Question Excel upload failed: Failed to save uploaded file error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    # 5. Run the advanced import pipeline
    image_dir = os.path.join("uploads", "question_images")
    original_dir = os.path.join("uploads", "question_images", "original")
    os.makedirs(image_dir, exist_ok=True)
    os.makedirs(original_dir, exist_ok=True)

    try:
        import_result = run_advanced_import(
            excel_path=stored_path,
            batch_id=batch_id,
            image_dir=image_dir,
            original_asset_dir=original_dir,
        )
    except Exception as e:
        log_error(f"Advanced import pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import pipeline failed: {str(e)}")

    total_rows = import_result.total_rows_inspected
    errors = import_result.errors
    valid_rows_to_insert = import_result.valid_rows
    success_count = len(valid_rows_to_insert)
    failed_count = len(errors)

    # Log asset conversion warnings
    for w in import_result.warnings:
        log_error(f"[Question Import Warning] {w}")

    # 6. 70-question constraint check
    if success_count != 70:
        log = ImportLog(
            upload_type="question_bank",
            file_name=file.filename,
            total_records=total_rows,
            success_count=0,
            failed_count=total_rows,
            error_details=json_error_details(
                department_id, dept.department_name, errors, replace_existing,
                f"Failed 70-question check. Got {success_count} valid rows. "
                f"Assets: {import_result.asset_stats}. "
                f"Conversion OK: {import_result.conversion_success}, "
                f"Failed: {import_result.conversion_failed}"
            ),
            uploaded_by=current_admin.id
        )
        db.add(log)
        db.commit()

        return QuestionUploadSummary(
            message=f"Question upload validation failed: Excel has {success_count} valid questions instead of exactly 70.",
            department_id=department_id,
            department_name=dept.department_name,
            total_rows=total_rows,
            success_count=0,
            failed_count=total_rows,
            replaced_existing=replace_existing,
            errors=[{"row": e["row"], "question_no": e["question_no"], "error": e["error"]} for e in errors]
        )

    # 7. Database transaction
    try:
        if replace_existing and active_questions_count > 0:
            db.query(Question).filter(
                and_(Question.department_id == department_id, Question.is_active == True)
            ).update({"is_active": False}, synchronize_session=False)

        for qr in valid_rows_to_insert:
            new_q = Question(
                department_id=department_id,
                question_no=qr["question_no"],
                question_text=qr["question_text"],
                option_a=qr["option_a"],
                option_b=qr["option_b"],
                option_c=qr["option_c"],
                option_d=qr["option_d"],
                correct_option=qr["correct_option"],
                marks=qr["marks"],
                is_active=True,
                import_batch_id=batch_id,
                image_path=qr.get("image_path")
            )
            db.add(new_q)

        asset_summary_str = (
            f"Assets: {import_result.asset_stats} | "
            f"Converted OK: {import_result.conversion_success} | "
            f"Failed: {import_result.conversion_failed} | "
            f"OMML→LaTeX: {import_result.omml_converted}"
        )

        log = ImportLog(
            upload_type="question_bank",
            file_name=file.filename,
            total_records=total_rows,
            success_count=success_count,
            failed_count=failed_count,
            error_details=json_error_details(
                department_id, dept.department_name, errors, replace_existing,
                f"Upload successful. {asset_summary_str}"
            ),
            uploaded_by=current_admin.id
        )
        db.add(log)
        db.commit()

        log_info(
            f"Question bank uploaded: dept={department_id}, batch={batch_id}, "
            f"questions={success_count}, {asset_summary_str}"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database transaction failed while inserting questions: {str(e)}"
        )

    # Build success message with asset stats
    asset_parts = []
    for fmt, cnt in import_result.asset_stats.items():
        if fmt != "TOTAL" and cnt > 0:
            asset_parts.append(f"{fmt}: {cnt}")

    asset_msg = f" | Assets extracted — {', '.join(asset_parts)}" if asset_parts else ""
    conv_warn = ""
    if import_result.conversion_failed > 0:
        conv_warn = f" | ⚠️ {import_result.conversion_failed} asset(s) failed conversion (check warnings)"

    return QuestionUploadSummary(
        message=f"Question bank uploaded successfully{asset_msg}{conv_warn}",
        department_id=department_id,
        department_name=dept.department_name,
        total_rows=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        replaced_existing=replace_existing,
        errors=[]
    )
# Old soft-delete routes removed in favor of permanent delete controls below


def json_error_details(dept_id: int, dept_name: str, errors: list, replace_existing: bool, status_msg: str) -> str:
    import json
    return json.dumps({
        "department_id": dept_id,
        "department_name": dept_name,
        "replace_existing": replace_existing,
        "status_message": status_msg,
        "errors": errors
    })

from pydantic import BaseModel

class QuestionBulkDeleteRequest(BaseModel):
    question_ids: List[int]

@router.delete("/bulk-delete")
def bulk_delete_questions(
    payload: QuestionBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Bulk delete questions and their candidate answers permanently."""
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can delete questions.")
    if not payload.question_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_ids list cannot be empty"
        )

    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # 1. Delete CandidateAnswer rows linked to questions
        answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.question_id.in_(payload.question_ids)).delete(synchronize_session=False)

        # 2. Delete Question rows
        questions_deleted = db.query(Question).filter(Question.id.in_(payload.question_ids)).delete(synchronize_session=False)

        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently bulk-deleted question IDs: {payload.question_ids}")

        return {
            "message": "Questions permanently deleted",
            "deleted_question_ids": payload.question_ids,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "questions": questions_deleted
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed bulk deleting questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while bulk deleting questions: {str(e)}"
        )

@router.delete("/department/{department_id}/hard-delete")
def hard_delete_department_questions(
    department_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Delete all Question rows from a department and their answers."""
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can delete questions.")
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # Get all question IDs for this department
        q_ids = [q.id for q in db.query(Question.id).filter(Question.department_id == department_id).all()]

        # 1. Delete CandidateAnswer rows related to questions from department
        answers_deleted = 0
        if q_ids:
            answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.question_id.in_(q_ids)).delete(synchronize_session=False)

        # 2. Delete all Question rows from department
        questions_deleted = db.query(Question).filter(Question.department_id == department_id).delete(synchronize_session=False)

        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently deleted entire question bank for department ID {department_id} (Code: {dept.department_code})")

        return {
            "message": "Question bank permanently deleted",
            "department_id": department_id,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "questions": questions_deleted
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed deleting department {department_id} questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while deleting department questions: {str(e)}"
        )

@router.delete("/{question_id}")
def delete_single_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Delete a single question and its candidate answers permanently."""
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can delete questions.")
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )

    from app.models.candidate_answer import CandidateAnswer
    import logging
    logger = logging.getLogger("phd_app")

    try:
        # 1. Delete CandidateAnswer rows linked to question
        answers_deleted = db.query(CandidateAnswer).filter(CandidateAnswer.question_id == question_id).delete(synchronize_session=False)

        # 2. Delete Question row
        q_no = question.question_no
        db.query(Question).filter(Question.id == question_id).delete(synchronize_session=False)
        db.commit()

        # Log admin event
        logger.info(f"Admin {current_admin.email} permanently deleted question ID {question_id} (No: {q_no})")

        return {
            "message": "Question permanently deleted",
            "question_id": question_id,
            "deleted_counts": {
                "candidate_answers": answers_deleted,
                "questions": 1
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed deleting question ID {question_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed while permanently deleting question: {str(e)}"
        )
