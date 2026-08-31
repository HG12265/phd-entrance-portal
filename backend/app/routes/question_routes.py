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
    if current_admin.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Only Super Admin can upload question banks.")
    # 1. Validate department
    dept = db.query(Department).filter(
        and_(Department.id == department_id, Department.is_active == True)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Active department not found.")
        
    # 2. Check if department already has active questions
    active_questions_count = db.query(Question).filter(
        and_(Question.department_id == department_id, Question.is_active == True)
    ).count()
    
    if active_questions_count > 0 and not replace_existing:
        raise HTTPException(
            status_code=400,
            detail="This department already has active questions. Use replace_existing=true to replace the question bank."
        )

    # 3. Save uploaded file
    from app.config import MAX_UPLOAD_SIZE_MB
    from app.logging_config import log_error

    # Validate file size
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
        
    batch_id = str(uuid.uuid4())
    stored_filename = f"{batch_id}{file_ext}"
    stored_path = os.path.join(UPLOAD_DIR, stored_filename)
    
    try:
        with open(stored_path, "wb") as f:
            f.write(file.file.read())
    except Exception as e:
        log_error(f"Question Excel upload failed: Failed to save uploaded file error={str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
        
    # 4. Load Excel using pandas
    try:
        df = pd.read_excel(stored_path, keep_default_na=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Excel file or format: {str(e)}")
        
    total_rows = len(df)

    # Normalize headers
    normalized_cols = [normalize_question_column_name(c) for c in df.columns]
    
    # Map headers to standard field names using COLUMN_MAPPING
    mapped_cols = []
    for col in normalized_cols:
        mapped_cols.append(COLUMN_MAPPING.get(col, col))
    df.columns = mapped_cols

    # Validate required columns
    ok, missing = validate_question_required_columns(df.columns)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns in Excel: {', '.join(missing)}"
        )

    # Build column index to field name mapping
    col_field_map = {}
    for idx, col_name in enumerate(df.columns):
        col_field_map[idx] = col_name

    # Extract images from Excel if present
    # Dictionary structure: row_field_images[row_num][field_name] = [list of image web URLs]
    row_field_images = {}
    image_dir = os.path.join("uploads", "question_images")
    os.makedirs(image_dir, exist_ok=True)
    
    import io
    from app.utils.image_converter import convert_image_bytes_to_png
    
    try:
        from app.services.excel_import.xlsx_inspector import extract_all_xlsx_media_images
        extracted_media = extract_all_xlsx_media_images(stored_path, image_dir, batch_id)
        # If openpyxl misses any media, map them to question rows if needed
    except Exception as inspect_err:
        from app.logging_config import log_error
        log_error(f"XLSX Media inspection warning: {inspect_err}")

    try:
        from openpyxl import load_workbook
        wb = load_workbook(stored_path)
        ws = wb.active
        if hasattr(ws, '_images') and ws._images:
            for img in ws._images:
                row_num = None
                col_num = 0
                if hasattr(img, 'anchor'):
                    anchor = img.anchor
                    if isinstance(anchor, str):
                        import re
                        match = re.search(r'\d+', anchor)
                        if match:
                            row_num = int(match.group())
                    elif hasattr(anchor, '_from'):
                        row_num = anchor._from.row + 1
                        col_num = getattr(anchor._from, 'col', 0)
                
                if row_num is not None:
                    field_name = col_field_map.get(col_num, "question_text")
                    if field_name not in ["question_text", "option_a", "option_b", "option_c", "option_d"]:
                        field_name = "question_text"
                        
                    img_bytes = None
                    if hasattr(img, 'ref') and img.ref:
                        img.ref.seek(0)
                        img_bytes = img.ref.read()
                    elif hasattr(img, '_data') and callable(img._data):
                        img_bytes = img._data()
                    elif hasattr(img, 'image') and img.image:
                        buf = io.BytesIO()
                        img.image.save(buf, format=getattr(img.image, 'format', None) or 'PNG')
                        img_bytes = buf.getvalue()
                    elif hasattr(img, 'path') and os.path.exists(img.path):
                        with open(img.path, "rb") as f_img:
                            img_bytes = f_img.read()

                    if img_bytes:
                        img_filename = f"q_img_{batch_id}_r{row_num}_{field_name}_{uuid.uuid4().hex[:8]}.png"
                        img_path = os.path.join(image_dir, img_filename)
                        if convert_image_bytes_to_png(img_bytes, img_path):
                            web_url = f"/static/question_images/{img_filename}"
                            if row_num not in row_field_images:
                                row_field_images[row_num] = {}
                            if field_name not in row_field_images[row_num]:
                                row_field_images[row_num][field_name] = []
                            row_field_images[row_num][field_name].append(web_url)
    except Exception as img_err:
        from app.logging_config import log_error
        log_error(f"Failed to parse images from Excel: {str(img_err)}")
        
    # Check for duplicate question numbers inside Excel
    has_dups, dup_q_nos = detect_duplicate_question_numbers(df)
    
    errors = []
    valid_rows_to_insert = []
    seen_excel_q_nos = set()
    
    # Process and validate row by row
    for index, row in df.iterrows():
        row_number = index + 2  # Excel is 1-indexed, headers are row 1
        row_imgs = row_field_images.get(row_number, {})
        
        # Check duplicate inside excel check
        q_no_raw = row.get("question_no")
        q_no = None
        try:
            if not pd.isna(q_no_raw):
                q_no = int(float(q_no_raw))
        except:
            pass
            
        row_dict = row.to_dict()
        valid, err_msg, parsed_q_no = validate_question_row(row_dict, row_number, row_imgs)
        
        if not valid:
            errors.append({
                "row": row_number,
                "question_no": parsed_q_no,
                "error": err_msg
            })
            continue
            
        # Check for duplication inside the Excel sheet
        if parsed_q_no in seen_excel_q_nos:
            errors.append({
                "row": row_number,
                "question_no": parsed_q_no,
                "error": f"Duplicate question number '{parsed_q_no}' in this Excel file."
            })
            continue
            
        seen_excel_q_nos.add(parsed_q_no)
        
        # Build combined text + image tags for each field
        def build_field_content(field_name: str) -> str:
            raw = clean_question_text(row.get(field_name))
            urls = row_imgs.get(field_name, [])
            if not urls:
                return raw
            img_tags = "".join([f'<img src="{u}" alt="{field_name} image" />' for u in urls])
            if raw:
                return f"{raw}\n{img_tags}"
            return img_tags

        # Determine primary image_path for database column
        primary_image = None
        if row_imgs.get("question_text"):
            primary_image = row_imgs["question_text"][0]
        else:
            for f in ["option_a", "option_b", "option_c", "option_d"]:
                if row_imgs.get(f):
                    primary_image = row_imgs[f][0]
                    break

        # Assemble clean row properties
        clean_row = {
            "question_no": parsed_q_no,
            "question_text": build_field_content("question_text"),
            "option_a": build_field_content("option_a"),
            "option_b": build_field_content("option_b"),
            "option_c": build_field_content("option_c"),
            "option_d": build_field_content("option_d"),
            "correct_option": parse_correct_option(row.get("correct_option")),
            "marks": parse_marks(row.get("marks")),
            "image_path": primary_image
        }
        valid_rows_to_insert.append(clean_row)

        
    success_count = len(valid_rows_to_insert)
    failed_count = len(errors)

    # 70-Question validation constraint check
    if success_count != 70:
        # Create an import log representing this validation failure
        log = ImportLog(
            upload_type="question_bank",
            file_name=file.filename,
            total_records=total_rows,
            success_count=0,
            failed_count=total_rows,
            error_details=json_error_details(department_id, dept.department_name, errors, replace_existing, "Failed exactly 70 questions validation check. Got " + str(success_count) + " valid rows."),
            uploaded_by=current_admin.id
        )
        db.add(log)
        db.commit()
        
        # Return summary detailing validation errors
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

    # Perform Database Transaction insertion
    try:
        # If replace_existing=True, soft deactivate old questions
        if replace_existing and active_questions_count > 0:
            db.query(Question).filter(
                and_(Question.department_id == department_id, Question.is_active == True)
            ).update({"is_active": False}, synchronize_session=False)

        # Bulk insert new questions
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
            
        # Log successful import in import_logs
        log = ImportLog(
            upload_type="question_bank",
            file_name=file.filename,
            total_records=total_rows,
            success_count=success_count,
            failed_count=failed_count,
            error_details=json_error_details(department_id, dept.department_name, errors, replace_existing, "Upload successful"),
            uploaded_by=current_admin.id
        )
        db.add(log)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database transaction failed while inserting questions: {str(e)}"
        )
        
    return QuestionUploadSummary(
        message="Question bank uploaded successfully",
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
