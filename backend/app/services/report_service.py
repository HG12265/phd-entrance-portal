from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
import json
import pandas as pd
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, List

from app.models.candidate import Candidate
from app.models.department import Department
from app.models.exam_session import ExamSession
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer
from app.models.question import Question

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

kolkata_tz = ZoneInfo("Asia/Kolkata")

def _map_result_status_filter(status: Optional[str]) -> Optional[str]:
    if status == "QUALIFIED":
        return "PASS"
    elif status == "NOT QUALIFIED":
        return "FAIL"
    return status

def _format_result_status_response(status: Optional[str]) -> Optional[str]:
    if status == "PASS":
        return "QUALIFIED"
    elif status == "FAIL":
        return "NOT QUALIFIED"
    return status

def get_official_attempts_subquery(db: Session):
    """
    Returns a subquery identifying the IDs of the official exam attempts.
    An official attempt is the earliest completed attempt per candidate per session.
    """
    from sqlalchemy import and_, func
    
    # 1. Subquery to find the minimum submitted time per candidate + session
    sub_min_time = db.query(
        ExamAttempt.candidate_id,
        ExamAttempt.exam_session_id,
        func.min(ExamAttempt.submitted_time).label("min_submitted_time")
    ).filter(
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).group_by(
        ExamAttempt.candidate_id,
        ExamAttempt.exam_session_id
    ).subquery()

    # 2. Subquery to find the minimum ID among attempts with that minimum submitted time
    sub_official_id = db.query(
        func.min(ExamAttempt.id).label("official_id")
    ).join(
        sub_min_time,
        and_(
            ExamAttempt.candidate_id == sub_min_time.c.candidate_id,
            ExamAttempt.exam_session_id == sub_min_time.c.exam_session_id,
            ExamAttempt.submitted_time == sub_min_time.c.min_submitted_time
        )
    ).filter(
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    ).group_by(
        ExamAttempt.candidate_id,
        ExamAttempt.exam_session_id
    )

    return sub_official_id

def _apply_session_filter_to_candidate_query(db: Session, cand_query, exam_session_id: Optional[int]):
    if not exam_session_id:
        return cand_query
    session = db.query(ExamSession).filter(ExamSession.id == exam_session_id).first()
    if session:
        allowed_dept_ids = [dept.id for dept in session.departments]
        return cand_query.filter(
            or_(
                Candidate.exam_session_id == exam_session_id,
                and_(
                    Candidate.exam_session_id == None,
                    Candidate.department_id.in_(allowed_dept_ids)
                )
            )
        )
    else:
        return cand_query.filter(Candidate.exam_session_id == exam_session_id)

def get_report_summary(db: Session, exam_session_id: Optional[int] = None, department_id: Optional[int] = None) -> dict:
    """
    Computes summary performance metrics for active candidates matching filters.
    """
    # Base active candidates query
    cand_query = db.query(Candidate).filter(Candidate.is_active == True)
    if exam_session_id:
        cand_query = _apply_session_filter_to_candidate_query(db, cand_query, exam_session_id)
    if department_id:
        cand_query = cand_query.filter(Candidate.department_id == department_id)
    
    candidates = cand_query.all()
    total_candidates = len(candidates)
    if total_candidates == 0:
        return {
            "total_candidates": 0, "appeared": 0, "submitted": 0, "auto_submitted": 0,
            "absent": 0, "passed": 0, "failed": 0, "pass_percentage": 0.0,
            "average_score": 0.0, "highest_score": 0, "lowest_score": 0
        }

    cand_ids = [c.id for c in candidates]
    
    # Query attempts for these candidates using the official attempt subquery
    sub_official_id = get_official_attempts_subquery(db)
    attempt_query = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id.in_(cand_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        attempt_query = attempt_query.filter(ExamAttempt.exam_session_id == exam_session_id)
    if department_id:
        attempt_query = attempt_query.filter(ExamAttempt.department_id == department_id)

    attempts = attempt_query.all()
    
    appeared = len(attempts)
    submitted = sum(1 for a in attempts if a.status == "submitted")
    auto_submitted = sum(1 for a in attempts if a.status == "auto_submitted")
    absent = total_candidates - appeared
    
    passed = sum(1 for a in attempts if a.result_status in ("PASS", "QUALIFIED"))
    failed = sum(1 for a in attempts if a.result_status in ("FAIL", "NOT QUALIFIED"))
    
    pass_percentage = round((passed / appeared) * 100, 2) if appeared > 0 else 0.0
    
    scores = [a.score for a in attempts]
    average_score = round(sum(scores) / len(scores), 2) if len(scores) > 0 else 0.0
    highest_score = max(scores) if len(scores) > 0 else 0
    lowest_score = min(scores) if len(scores) > 0 else 0
    
    return {
        "total_candidates": total_candidates,
        "appeared": appeared,
        "submitted": submitted,
        "auto_submitted": auto_submitted,
        "absent": absent,
        "passed": passed,
        "failed": failed,
        "pass_percentage": pass_percentage,
        "average_score": average_score,
        "lowest_score": lowest_score,
        "highest_score": highest_score
    }

def get_subject_summary(db: Session, exam_session_id: Optional[int] = None) -> List[dict]:
    """
    Computes statistics breakdown grouped by academic department.
    """
    departments = db.query(Department).filter(Department.is_active == True).order_by(Department.department_name).all()
    results = []
    
    for dept in departments:
        # Check active questions registry count
        q_count = db.query(Question).filter(
            Question.department_id == dept.id,
            Question.is_active == True
        ).count()
        is_ready = q_count == 70
        
        summary = get_report_summary(db, exam_session_id=exam_session_id, department_id=dept.id)
        results.append({
            "department_id": dept.id,
            "department_name": dept.department_name,
            "total_candidates": summary["total_candidates"],
            "appeared": summary["appeared"],
            "absent": summary["absent"],
            "passed": summary["passed"],
            "failed": summary["failed"],
            "average_score": summary["average_score"],
            "highest_score": summary["highest_score"],
            "lowest_score": summary["lowest_score"],
            "is_question_bank_ready": is_ready
        })
        
    return results

def get_leaderboard_query(db: Session, department_id: Optional[int] = None, exam_session_id: Optional[int] = None, result_status: Optional[str] = None, search: Optional[str] = None):
    """
    Constructs base query for leaderboards sorted by criteria:
    score DESC, correct_count DESC, submitted_time ASC, application_number ASC.
    """
    result_status = _map_result_status_filter(result_status)
    sub_official_id = get_official_attempts_subquery(db)
    query = db.query(
        ExamAttempt, Candidate, Department
    ).join(
        Candidate, ExamAttempt.candidate_id == Candidate.id
    ).join(
        Department, Candidate.department_id == Department.id
    ).filter(
        Candidate.is_active == True,
        ExamAttempt.id.in_(sub_official_id)
    )
    
    if department_id:
        query = query.filter(ExamAttempt.department_id == department_id)
    if exam_session_id:
        query = query.filter(ExamAttempt.exam_session_id == exam_session_id)
    if result_status:
        query = query.filter(ExamAttempt.result_status == result_status)
    if search:
        query = query.filter(or_(
            Candidate.name.like(f"%{search}%"),
            Candidate.application_number.like(f"%{search}%")
        ))
        
    # Apply standard sorting
    query = query.order_by(
        ExamAttempt.score.desc(),
        ExamAttempt.correct_count.desc(),
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        Candidate.application_number.asc()
    )
    return query

def get_subject_leaderboard(db: Session, department_id: int, exam_session_id: Optional[int] = None, result_status: Optional[str] = None, search: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
    """
    Returns subject-wise leaderboard pagination payload.
    """
    query = get_leaderboard_query(db, department_id=department_id, exam_session_id=exam_session_id, result_status=result_status, search=search)
    return paginate_leaderboard(query, page, limit)

def get_overall_leaderboard(db: Session, department_id: Optional[int] = None, exam_session_id: Optional[int] = None, result_status: Optional[str] = None, search: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
    """
    Returns overall leaderboard pagination payload.
    """
    query = get_leaderboard_query(db, department_id=department_id, exam_session_id=exam_session_id, result_status=result_status, search=search)
    return paginate_leaderboard(query, page, limit)

def paginate_leaderboard(query, page: int, limit: int) -> dict:
    """Helper to paginate leaderboard records and compute ranks."""
    total = query.count()
    pages = (total + limit - 1) // limit if total > 0 else 0
    offset = (page - 1) * limit
    
    rows = query.offset(offset).limit(limit).all()
    
    items = []
    for idx, (attempt, cand, dept) in enumerate(rows):
        sub_time = attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.submitted_time else None
        items.append({
            "rank": offset + idx + 1,
            "candidate_id": cand.id,
            "application_number": cand.application_number,
            "name": cand.name,
            "department_name": dept.department_name,
            "score": attempt.score,
            "total_marks": 70,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "result_status": _format_result_status_response(attempt.result_status),
            "submission_type": attempt.submission_type,
            "submitted_time": sub_time,
            "login_time": attempt.login_time.replace(tzinfo=kolkata_tz).isoformat() if getattr(attempt, "login_time", None) else None,
            "system_ip": getattr(attempt, "system_ip", None) or "N/A",
            "time_taken": calculate_time_taken(getattr(attempt, "login_time", None), attempt.submitted_time)
        })
        
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

def get_absentees(db: Session, exam_session_id: Optional[int] = None, department_id: Optional[int] = None, search: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
    """
    Returns list of active candidates who have not submitted any exam attempts.
    """
    # Subquery for submitted candidates matching constraints
    sub_official_id = get_official_attempts_subquery(db)
    sub = db.query(ExamAttempt.candidate_id).filter(
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        sub = sub.filter(ExamAttempt.exam_session_id == exam_session_id)
        
    query = db.query(Candidate, Department, ExamSession).join(
        Department, Candidate.department_id == Department.id
    ).outerjoin(
        ExamSession, Candidate.exam_session_id == ExamSession.id
    ).filter(
        Candidate.is_active == True,
        ~Candidate.id.in_(sub)
    )
    
    if department_id:
        query = query.filter(Candidate.department_id == department_id)
    if exam_session_id:
        query = _apply_session_filter_to_candidate_query(db, query, exam_session_id)
    if search:
        query = query.filter(or_(
            Candidate.name.like(f"%{search}%"),
            Candidate.application_number.like(f"%{search}%")
        ))
        
    total = query.count()
    pages = (total + limit - 1) // limit if total > 0 else 0
    offset = (page - 1) * limit
    
    rows = query.offset(offset).limit(limit).all()
    items = []
    for cand, dept, session in rows:
        items.append({
            "candidate_id": cand.id,
            "application_number": cand.application_number,
            "name": cand.name,
            "email": cand.email,
            "mobile_number": cand.mobile_number,
            "department_name": dept.department_name,
            "exam_session_name": session.session_name if session else "N/A"
        })
        
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

def get_candidate_report(db: Session, candidate_id: int, exam_session_id: Optional[int] = None) -> dict:
    """
    Gathers detailed exam report data for a specific candidate.
    Includes question-wise correct answers and options (restricted to admin view).
    """
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
        
    dept = db.query(Department).filter(Department.id == cand.department_id).first()
    dept_name = dept.department_name if dept else "N/A"
    
    # Session Details
    sess_id = exam_session_id if exam_session_id else cand.exam_session_id
    session = None
    if sess_id:
        session = db.query(ExamSession).filter(ExamSession.id == sess_id).first()
        
    if not session:
        # Fallback to resolving the single active session if cand unassigned
        session = db.query(ExamSession).filter(ExamSession.is_active == True).first()

    # Locate attempt using the official order: earliest submitted, smallest ID
    attempt_query = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id == cand.id,
        ExamAttempt.status.in_(["submitted", "auto_submitted"])
    )
    if sess_id:
        attempt_query = attempt_query.filter(ExamAttempt.exam_session_id == sess_id)
        
    attempt = attempt_query.order_by(
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        ExamAttempt.id.asc()
    ).first()
    
    candidate_info = {
        "id": cand.id,
        "application_number": cand.application_number,
        "name": cand.name,
        "email": cand.email,
        "mobile_number": cand.mobile_number,
        "dob": cand.dob.isoformat() if cand.dob else None,
        "department_name": dept_name,
        "photo_url": f"/static/candidate_photos/{cand.photo_filename}" if cand.photo_filename else None
    }
    
    exam_info = {
        "session_name": session.session_name if session else "N/A",
        "exam_title": session.exam_title if session else "PhD Entrance Examination",
        "start_time": session.start_time.replace(tzinfo=kolkata_tz).isoformat() if session else None,
        "end_time": session.end_time.replace(tzinfo=kolkata_tz).isoformat() if session else None,
        "duration_minutes": session.duration_minutes if session else 90,
        "total_questions": 70,
        "total_marks": 70,
        "pass_mark": 28
    }
    
    if not attempt:
        return {
            "candidate": candidate_info,
            "exam": exam_info,
            "attempt": None,
            "answers": [],
            "message": "Candidate did not attend the exam"
        }
        
    # Restore question orders and answers
    try:
        shuffled_ids = json.loads(attempt.shuffled_question_order)
    except Exception:
        shuffled_ids = []
        
    answers = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt.id).all()
    answer_map = {ans.question_id: ans for ans in answers}
    
    questions = db.query(Question).filter(Question.id.in_(shuffled_ids)).all()
    question_map = {q.id: q for q in questions}
    
    response_answers = []
    for idx, q_id in enumerate(shuffled_ids):
        q = question_map.get(q_id)
        if not q:
            continue
        ans = answer_map.get(q_id)
        
        response_answers.append({
            "display_no": idx + 1,
            "question_id": q.id,
            "question_no": q.question_no,
            "question_text": q.question_text,
            "question_tamil": getattr(q, "question_tamil", None),
            "option_a": q.option_a,
            "option_b": q.option_b,
            "option_c": q.option_c,
            "option_d": q.option_d,
            "candidate_answer": ans.selected_option if ans else None,
            "correct_answer": q.correct_option,
            "is_correct": ans.is_correct if ans else False,
            "mark_awarded": ans.mark_awarded if ans else 0,
            "answer_status": ans.answer_status if ans else "not_visited"
        })
        
    attempt_info = {
        "attempt_id": attempt.id,
        "status": attempt.status,
        "submission_type": attempt.submission_type,
        "start_time": attempt.start_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.start_time else None,
        "end_time": attempt.end_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.end_time else None,
        "submitted_time": attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.submitted_time else None,
        "score": attempt.score,
        "correct_count": attempt.correct_count,
        "wrong_count": attempt.wrong_count,
        "unanswered_count": attempt.unanswered_count,
        "result_status": _format_result_status_response(attempt.result_status)
    }
    
    return {
        "candidate": candidate_info,
        "exam": exam_info,
        "attempt": attempt_info,
        "answers": response_answers
    }

def get_attempt_report(db: Session, attempt_id: int) -> dict:
    """
    Retrieve candidate score report looking up by attempt_id.
    """
    attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Exam attempt not found.")
    return get_candidate_report(db, attempt.candidate_id, attempt.exam_session_id)

def calculate_time_taken(login_time, submitted_time) -> str:
    if not login_time or not submitted_time:
        return "--"
    delta = submitted_time - login_time
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        total_seconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def format_export_rows(rows) -> list:
    export_data = []
    for attempt, cand, dept in rows:
        login_time_formatted = attempt.login_time.strftime("%d-%m-%Y %H:%M:%S") if getattr(attempt, "login_time", None) else "N/A"
        submitted_time_formatted = attempt.submitted_time.strftime("%d-%m-%Y %H:%M:%S") if attempt.submitted_time else "N/A"
        time_taken = calculate_time_taken(getattr(attempt, "login_time", None), attempt.submitted_time)
        qualified_status = _format_result_status_response(attempt.result_status)
        
        export_data.append({
            "Application ID": cand.application_id or cand.application_number or "",
            "Applicant Name": cand.applicant_name or cand.name or "",
            "Department": dept.department_name,
            "Programme Offered": cand.programme_offered or "",
            "Subject": cand.subject or "",
            "Category": cand.category_ft_pt or "",
            "Score": attempt.score,
            "Correct": attempt.correct_count,
            "Wrong": attempt.wrong_count,
            "Unanswered": attempt.unanswered_count,
            "Qualified Status": qualified_status,
            "Submission Type": (attempt.submission_type.capitalize() if attempt.submission_type else "N/A"),
            "Login Time": login_time_formatted,
            "Submitted Time": submitted_time_formatted,
            "Time Taken": time_taken,
            "System IP": getattr(attempt, "system_ip", None) or "N/A"
        })
    return export_data

def export_leaderboard_excel(db: Session, department_id: Optional[int] = None, exam_session_id: Optional[int] = None, result_status: Optional[str] = None) -> bytes:
    """
    Generates Excel sheets of leaderboard results in memory.
    """
    query = get_leaderboard_query(db, department_id=department_id, exam_session_id=exam_session_id, result_status=result_status)
    rows = query.all()
    
    export_data = format_export_rows(rows)
        
    df = pd.DataFrame(export_data)
    
    # Handle empty dataset columns
    if df.empty:
        df = pd.DataFrame(columns=[
            "Application ID", "Applicant Name", "Department",
            "Programme Offered", "Subject", "Category", "Score",
            "Correct", "Wrong", "Unanswered", "Qualified Status", "Submission Type",
            "Login Time", "Submitted Time", "Time Taken", "System IP"
        ])
        
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Leaderboard")
        ws = writer.sheets["Leaderboard"]
        ws.protection.sheet = True
        ws.protection.password = "MCA2026"
    return out.getvalue()

def export_absentees_excel(db: Session, department_id: Optional[int] = None, exam_session_id: Optional[int] = None) -> bytes:
    """
    Generates Excel sheet listing absent candidates in memory.
    """
    # Subquery for submitted candidates matching constraints
    sub_official_id = get_official_attempts_subquery(db)
    sub = db.query(ExamAttempt.candidate_id).filter(
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        sub = sub.filter(ExamAttempt.exam_session_id == exam_session_id)
        
    query = db.query(Candidate, Department, ExamSession).join(
        Department, Candidate.department_id == Department.id
    ).outerjoin(
        ExamSession, Candidate.exam_session_id == ExamSession.id
    ).filter(
        Candidate.is_active == True,
        ~Candidate.id.in_(sub)
    )
    
    if department_id:
        query = query.filter(Candidate.department_id == department_id)
    if exam_session_id:
        query = _apply_session_filter_to_candidate_query(db, query, exam_session_id)
        
    rows = query.all()
    export_data = []
    for cand, dept, session in rows:
        export_data.append({
            "Application ID": cand.application_id or cand.application_number or "",
            "Applicant Name": cand.applicant_name or cand.name or "",
            "Department": dept.department_name,
            "Programme Offered": cand.programme_offered or "",
            "Subject": cand.subject or "",
            "Category": cand.category_ft_pt or "",
            "Score": "N/A",
            "Correct": "N/A",
            "Wrong": "N/A",
            "Unanswered": "N/A",
            "Qualified Status": "N/A",
            "Submission Type": "N/A",
            "Login Time": "N/A",
            "Submitted Time": "N/A",
            "Time Taken": "--",
            "System IP": "N/A"
        })
        
    df = pd.DataFrame(export_data)
    if df.empty:
        df = pd.DataFrame(columns=[
            "Application ID", "Applicant Name", "Department",
            "Programme Offered", "Subject", "Category", "Score",
            "Correct", "Wrong", "Unanswered", "Qualified Status", "Submission Type",
            "Login Time", "Submitted Time", "Time Taken", "System IP"
        ])
        
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Absentees")
        ws = writer.sheets["Absentees"]
        ws.protection.sheet = True
        ws.protection.password = "MCA2026"
    return out.getvalue()

def export_candidate_pdf(db: Session, candidate_id: int, exam_session_id: Optional[int] = None) -> bytes:
    """
    Generates Candidate Evaluation PDF report sheet in-memory.
    """
    report = get_candidate_report(db, candidate_id, exam_session_id)
    cand = report["candidate"]
    exam = report["exam"]
    attempt = report["attempt"]
    answers = report["answers"]
    
    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1e3a8a')
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#0f766e'), spaceBefore=10, spaceAfter=5
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.HexColor('#334155')
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=13, textColor=colors.white
    )
    
    story = []
    
    # Document Header
    story.append(Paragraph("PhD Entrance Examination - Evaluation Card", title_style))
    story.append(Spacer(1, 15))
    
    # Profile & Exam Information Grid
    data_profile = [
        [
            Paragraph(f"<b>Candidate Name:</b> {cand['name']}", body_style),
            Paragraph(f"<b>Application Number:</b> {cand['application_number']}", body_style)
        ],
        [
            Paragraph(f"<b>Department Subject:</b> {cand['department_name']}", body_style),
            Paragraph(f"<b>Email Address:</b> {cand['email'] if cand['email'] else 'N/A'}", body_style)
        ],
        [
            Paragraph(f"<b>Exam Scheduled Session:</b> {exam['session_name']}", body_style),
            Paragraph(f"<b>Scheduled Date/Time:</b> {exam['exam_title']}", body_style)
        ]
    ]
    t_profile = Table(data_profile, colWidths=[270, 270])
    t_profile.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t_profile)
    story.append(Spacer(1, 15))
    
    # Score Summary Banner
    story.append(Paragraph("Performance & Grading Results", section_style))
    if attempt:
        status_color = '#10b981' if attempt['result_status'] in ('PASS', 'QUALIFIED') else '#ef4444'
        sub_type_label = "Manual Submit" if attempt['submission_type'] == 'manual' else "Auto Submit"
        sub_time = attempt['submitted_time'][:16].replace('T', ' ') if attempt['submitted_time'] else 'N/A'
        
        data_score = [
            [
                Paragraph("<b>Total Score Obtained</b>", body_style),
                Paragraph("<b>Passing Status</b>", body_style),
                Paragraph("<b>Submission Mode</b>", body_style),
                Paragraph("<b>Evaluation Date</b>", body_style)
            ],
            [
                Paragraph(f"<font size=14 color='#1e3a8a'><b>{attempt['score']} / 70</b></font>", body_style),
                Paragraph(f"<font size=14 color='{status_color}'><b>{attempt['result_status']}</b></font>", body_style),
                Paragraph(f"{sub_type_label}", body_style),
                Paragraph(f"{sub_time}", body_style)
            ],
            [
                Paragraph(f"Correct Answers: <b>{attempt['correct_count']}</b>", body_style),
                Paragraph(f"Wrong Answers: <b>{attempt['wrong_count']}</b>", body_style),
                Paragraph(f"Unanswered: <b>{attempt['unanswered_count']}</b>", body_style),
                Paragraph("", body_style)
            ]
        ]
        t_score = Table(data_score, colWidths=[135, 135, 135, 135])
        t_score.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f0fdf4') if attempt['result_status'] in ('PASS', 'QUALIFIED') else colors.HexColor('#fef2f2')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bbf7d0') if attempt['result_status'] in ('PASS', 'QUALIFIED') else colors.HexColor('#fca5a5')),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dcfce7') if attempt['result_status'] in ('PASS', 'QUALIFIED') else colors.HexColor('#fee2e2')),
        ]))
        story.append(t_score)
    else:
        story.append(Paragraph("<font color='#b91c1c'><b>Candidate was absent for this examination. No attempt logs recorded.</b></font>", body_style))
        
    story.append(Spacer(1, 15))
    
    # Answers Table
    if attempt and answers:
        story.append(Paragraph("Question-Wise Evaluation Logs", section_style))
        table_data = [[
            Paragraph("Q.No", header_style),
            Paragraph("Question Details", header_style),
            Paragraph("Candidate Answer", header_style),
            Paragraph("Correct Answer", header_style),
            Paragraph("Status", header_style),
            Paragraph("Mark", header_style)
        ]]
        
        for ans in answers:
            # Strip LaTeX symbols out or map safely for basic text PDF rendering
            clean_text = ans["question_text"]
            # Truncate long question texts to fit in PDF cells safely
            if len(clean_text) > 130:
                clean_text = clean_text[:127] + "..."
            
            ans_status_label = "Correct" if ans["is_correct"] else ("Wrong" if ans["candidate_answer"] else "Unanswered")
            ans_color = '#15803d' if ans["is_correct"] else ('#b91c1c' if ans["candidate_answer"] else '#475569')
            
            table_data.append([
                Paragraph(str(ans["display_no"]), body_style),
                Paragraph(clean_text, body_style),
                Paragraph(ans["candidate_answer"] if ans["candidate_answer"] else "-", body_style),
                Paragraph(ans["correct_answer"], body_style),
                Paragraph(f"<font color='{ans_color}'><b>{ans_status_label}</b></font>", body_style),
                Paragraph(str(ans["mark_awarded"]), body_style)
            ])
            
        t_answers = Table(table_data, colWidths=[35, 230, 80, 80, 85, 30])
        t_answers.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
            ('PADDING', (0,0), (-1,-1), 4),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ]))
        story.append(t_answers)
        
    doc.build(story)
    return out.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 15 — Simplified Accurate Reports
# ─────────────────────────────────────────────────────────────────────────────

def _get_session_candidate_ids(db: Session, exam_session_id: Optional[int], department_id: Optional[int] = None):
    """
    Return candidate_ids for the given session filter.
    Session-safe: if a session is specified, include candidates explicitly assigned
    to it, plus candidates with no explicit session assignment (NULL) whose department
    is allowed in that session.
    """
    q = db.query(Candidate).filter(Candidate.is_active == True)
    if department_id:
        q = q.filter(Candidate.department_id == department_id)

    if exam_session_id:
        q = _apply_session_filter_to_candidate_query(db, q, exam_session_id)
    # If no session filter: include everyone

    candidates = q.all()
    cand_ids = [c.id for c in candidates]
    return cand_ids


def get_overall_result(
    db: Session,
    exam_session_id: Optional[int] = None,
    department_id: Optional[int] = None,
    result_status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50
) -> dict:
    """
    Phase 15: Returns overall summary + paginated candidate result table.
    Uses official attempt logic (Phase 13). Respects Phase 14 force-reopen.
    """
    result_status = _map_result_status_filter(result_status)
    cand_ids = _get_session_candidate_ids(db, exam_session_id, department_id)
    total_registered = len(cand_ids)

    sub_official_id = get_official_attempts_subquery(db)

    # Base attempt query
    att_q = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id.in_(cand_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        att_q = att_q.filter(ExamAttempt.exam_session_id == exam_session_id)

    all_attempts = att_q.all()
    appeared = len(all_attempts)
    absent = total_registered - appeared
    passed = sum(1 for a in all_attempts if a.result_status in ("PASS", "QUALIFIED"))
    failed = sum(1 for a in all_attempts if a.result_status in ("FAIL", "NOT QUALIFIED"))
    pass_pct = round(passed / appeared * 100, 1) if appeared > 0 else 0.0
    scores = [a.score for a in all_attempts]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    highest = max(scores) if scores else 0
    lowest = min(scores) if scores else 0

    summary = {
        "total_registered": total_registered,
        "appeared": appeared,
        "absent": absent,
        "passed": passed,
        "failed": failed,
        "pass_percentage": pass_pct,
        "average_score": avg_score,
        "lowest_score": lowest,
        "highest_score": highest
    }

    # Build result table query with joins
    result_q = db.query(ExamAttempt, Candidate, Department).join(
        Candidate, ExamAttempt.candidate_id == Candidate.id
    ).join(
        Department, Candidate.department_id == Department.id
    ).filter(
        Candidate.is_active == True,
        ExamAttempt.candidate_id.in_(cand_ids),
        ExamAttempt.id.in_(sub_official_id)
    )

    if exam_session_id:
        result_q = result_q.filter(ExamAttempt.exam_session_id == exam_session_id)
    if department_id:
        result_q = result_q.filter(Candidate.department_id == department_id)
    if result_status:
        result_q = result_q.filter(ExamAttempt.result_status == result_status)
    if search:
        s = f"%{search}%"
        result_q = result_q.filter(or_(
            Candidate.application_id.like(s),
            Candidate.application_number.like(s),
            Candidate.applicant_name.like(s),
            Candidate.name.like(s)
        ))

    result_q = result_q.order_by(
        ExamAttempt.score.desc(),
        ExamAttempt.correct_count.desc(),
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        Candidate.application_number.asc()
    )

    total_results = result_q.count()
    pages = (total_results + limit - 1) // limit if total_results > 0 else 0
    rows = result_q.offset((page - 1) * limit).limit(limit).all()

    results = []
    for rank_idx, (attempt, cand, dept) in enumerate(rows):
        sub_time = attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.submitted_time else None
        results.append({
            "rank": (page - 1) * limit + rank_idx + 1,
            "candidate_id": cand.id,
            "application_id": cand.application_id or cand.application_number,
            "applicant_name": cand.applicant_name or cand.name,
            "initial": cand.initial or "",
            "department_name": dept.department_name,
            "programme_offered": cand.programme_offered or "",
            "subject": cand.subject or "",
            "category_ft_pt": cand.category_ft_pt or "",
            "score": attempt.score,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "result_status": _format_result_status_response(attempt.result_status),
            "submission_type": attempt.submission_type,
            "submitted_time": sub_time,
            "login_time": attempt.login_time.replace(tzinfo=kolkata_tz).isoformat() if getattr(attempt, "login_time", None) else None,
            "system_ip": getattr(attempt, "system_ip", None) or "N/A",
            "time_taken": calculate_time_taken(getattr(attempt, "login_time", None), attempt.submitted_time)
        })

    return {
        "summary": summary,
        "results": results,
        "total": total_results,
        "page": page,
        "limit": limit,
        "pages": pages
    }


def get_department_wise_report(db: Session, exam_session_id: Optional[int] = None) -> dict:
    """
    Phase 15: Returns department-wise report table with correct formulas.
    """
    departments = db.query(Department).filter(Department.is_active == True).order_by(Department.department_name).all()
    sub_official_id = get_official_attempts_subquery(db)

    report = []
    for dept in departments:
        # Registered: session-safe
        reg_ids = _get_session_candidate_ids(db, exam_session_id, department_id=dept.id)
        registered = len(reg_ids)

        # Appeared: official attempts for these candidates
        att_q = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id.in_(reg_ids),
            ExamAttempt.id.in_(sub_official_id)
        )
        if exam_session_id:
            att_q = att_q.filter(ExamAttempt.exam_session_id == exam_session_id)

        dept_attempts = att_q.all()
        appeared = len(dept_attempts)
        absent = registered - appeared
        passed = sum(1 for a in dept_attempts if a.result_status == "PASS")
        failed = sum(1 for a in dept_attempts if a.result_status == "FAIL")
        pass_pct = round(passed / appeared * 100, 1) if appeared > 0 else 0.0
        scores = [a.score for a in dept_attempts]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        highest = max(scores) if scores else 0
        lowest = min(scores) if scores else 0

        # Question bank
        q_count = db.query(Question).filter(
            Question.department_id == dept.id,
            Question.is_active == True
        ).count()
        q_status = f"70/70 Ready" if q_count == 70 else f"{q_count}/70 Pending"

        report.append({
            "department_id": dept.id,
            "department_name": dept.department_name,
            "registered": registered,
            "appeared": appeared,
            "absent": absent,
            "passed": passed,
            "failed": failed,
            "pass_percentage": pass_pct,
            "average_score": avg_score,
            "highest_score": highest,
            "lowest_score": lowest,
            "question_count": q_count,
            "question_bank_status": q_status
        })

    return {"departments": report}


def get_department_detail(
    db: Session,
    department_id: int,
    exam_session_id: Optional[int] = None,
    result_status: Optional[str] = None,
    search: Optional[str] = None
) -> dict:
    """
    Phase 15: Returns full detail for a single department — summary, results, absentees.
    """
    result_status = _map_result_status_filter(result_status)
    dept = db.query(Department).filter(Department.id == department_id).first()
    if not dept:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Department not found")

    reg_ids = _get_session_candidate_ids(db, exam_session_id, department_id=department_id)
    registered = len(reg_ids)

    sub_official_id = get_official_attempts_subquery(db)
    att_q = db.query(ExamAttempt).filter(
        ExamAttempt.candidate_id.in_(reg_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        att_q = att_q.filter(ExamAttempt.exam_session_id == exam_session_id)

    dept_attempts = att_q.all()
    appeared = len(dept_attempts)
    absent = registered - appeared
    passed = sum(1 for a in dept_attempts if a.result_status in ("PASS", "QUALIFIED"))
    failed = sum(1 for a in dept_attempts if a.result_status in ("FAIL", "NOT QUALIFIED"))
    pass_pct = round(passed / appeared * 100, 1) if appeared > 0 else 0.0
    scores = [a.score for a in dept_attempts]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    highest = max(scores) if scores else 0
    lowest = min(scores) if scores else 0

    summary = {
        "registered": registered, "appeared": appeared, "absent": absent,
        "passed": passed, "failed": failed, "pass_percentage": pass_pct,
        "average_score": avg_score, "lowest_score": lowest, "highest_score": highest
    }

    # Results table
    result_q = db.query(ExamAttempt, Candidate).join(
        Candidate, ExamAttempt.candidate_id == Candidate.id
    ).filter(
        Candidate.is_active == True,
        ExamAttempt.candidate_id.in_(reg_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    if exam_session_id:
        result_q = result_q.filter(ExamAttempt.exam_session_id == exam_session_id)
    if result_status:
        result_q = result_q.filter(ExamAttempt.result_status == result_status)
    if search:
        s = f"%{search}%"
        result_q = result_q.filter(or_(
            Candidate.application_id.like(s),
            Candidate.application_number.like(s),
            Candidate.applicant_name.like(s),
            Candidate.name.like(s)
        ))
    result_q = result_q.order_by(
        ExamAttempt.score.desc(),
        ExamAttempt.correct_count.desc(),
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        Candidate.application_number.asc()
    )
    rows = result_q.all()
    results = []
    for rank_idx, (attempt, cand) in enumerate(rows):
        sub_time = attempt.submitted_time.replace(tzinfo=kolkata_tz).isoformat() if attempt.submitted_time else None
        results.append({
            "rank": rank_idx + 1,
            "candidate_id": cand.id,
            "application_id": cand.application_id or cand.application_number,
            "applicant_name": cand.applicant_name or cand.name,
            "initial": cand.initial or "",
            "programme_offered": cand.programme_offered or "",
            "subject": cand.subject or "",
            "category_ft_pt": cand.category_ft_pt or "",
            "score": attempt.score,
            "correct_count": attempt.correct_count,
            "wrong_count": attempt.wrong_count,
            "unanswered_count": attempt.unanswered_count,
            "result_status": _format_result_status_response(attempt.result_status),
            "submitted_time": sub_time,
            "login_time": attempt.login_time.replace(tzinfo=kolkata_tz).isoformat() if getattr(attempt, "login_time", None) else None,
            "system_ip": getattr(attempt, "system_ip", None) or "N/A",
            "time_taken": calculate_time_taken(getattr(attempt, "login_time", None), attempt.submitted_time)
        })

    # Absentees: registered candidates without official attempt
    appeared_cand_ids = set(a.candidate_id for a in dept_attempts)
    absentee_ids = [cid for cid in reg_ids if cid not in appeared_cand_ids]
    absentee_cands = db.query(Candidate).filter(Candidate.id.in_(absentee_ids)).all()
    absentees = [{
        "application_id": c.application_id or c.application_number,
        "applicant_name": c.applicant_name or c.name,
        "initial": c.initial or "",
        "mobile_number": c.mobile_number or "",
        "email": c.email or "",
        "category_ft_pt": c.category_ft_pt or "",
        "programme_offered": c.programme_offered or "",
        "subject": c.subject or ""
    } for c in absentee_cands]

    return {
        "department": {"id": dept.id, "name": dept.department_name},
        "summary": summary,
        "results": results,
        "absentees": absentees
    }


def export_overall_result_excel(
    db: Session,
    exam_session_id: Optional[int] = None,
    department_id: Optional[int] = None,
    result_status: Optional[str] = None
) -> bytes:
    """Phase 15: Export overall result table as Excel with Phase 18 fields."""
    result_status = _map_result_status_filter(result_status)
    cand_ids = _get_session_candidate_ids(db, exam_session_id, department_id)
    sub_official_id = get_official_attempts_subquery(db)
    
    result_q = db.query(ExamAttempt, Candidate, Department).join(
        Candidate, ExamAttempt.candidate_id == Candidate.id
    ).join(
        Department, Candidate.department_id == Department.id
    ).filter(
        Candidate.is_active == True,
        ExamAttempt.candidate_id.in_(cand_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    
    if exam_session_id:
        result_q = result_q.filter(ExamAttempt.exam_session_id == exam_session_id)
    if department_id:
        result_q = result_q.filter(Candidate.department_id == department_id)
    if result_status:
        result_q = result_q.filter(ExamAttempt.result_status == result_status)
        
    result_q = result_q.order_by(
        ExamAttempt.score.desc(),
        ExamAttempt.correct_count.desc(),
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        Candidate.application_number.asc()
    )
    
    rows = result_q.all()
    export_data = format_export_rows(rows)
    
    df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=[
        "Application ID", "Applicant Name", "Department",
        "Programme Offered", "Subject", "Category", "Score",
        "Correct", "Wrong", "Unanswered", "Qualified Status", "Submission Type",
        "Login Time", "Submitted Time", "Time Taken", "System IP"
    ])
    
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Overall Result")
        ws = writer.sheets["Overall Result"]
        ws.protection.sheet = True
        ws.protection.password = "MCA2026"
    return out.getvalue()


def export_department_wise_excel(db: Session, exam_session_id: Optional[int] = None) -> bytes:
    """Phase 15: Export department-wise summary as Excel."""
    data = get_department_wise_report(db, exam_session_id)
    export_data = []
    for idx, d in enumerate(data["departments"]):
        export_data.append({
            "S.No": idx + 1,
            "Department": d["department_name"],
            "Registered": d["registered"],
            "Appeared": d["appeared"],
            "Absent": d["absent"],
            "Qualified": d["passed"],
            "Not Qualified": d["failed"],
            "Qualified %": d["pass_percentage"],
            "Avg Score": d["average_score"],
            "Lowest Score": d["lowest_score"],
            "Highest Score": d["highest_score"],
            "Question Bank": d["question_bank_status"]
        })
    df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=[
        "S.No", "Department", "Registered", "Appeared", "Absent",
        "Qualified", "Not Qualified", "Qualified %", "Avg Score",
        "Lowest Score", "Highest Score", "Question Bank"
    ])
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Department Summary")
        ws = writer.sheets["Department Summary"]
        ws.protection.sheet = True
        ws.protection.password = "MCA2026"
    return out.getvalue()


def export_department_report_excel(
    db: Session,
    department_id: int,
    exam_session_id: Optional[int] = None,
    result_status: Optional[str] = None
) -> bytes:
    """Phase 15: Export selected department candidate result as Excel."""
    result_status = _map_result_status_filter(result_status)
    reg_ids = _get_session_candidate_ids(db, exam_session_id, department_id=department_id)
    sub_official_id = get_official_attempts_subquery(db)
    
    result_q = db.query(ExamAttempt, Candidate, Department).join(
        Candidate, ExamAttempt.candidate_id == Candidate.id
    ).join(
        Department, Candidate.department_id == Department.id
    ).filter(
        Candidate.is_active == True,
        ExamAttempt.candidate_id.in_(reg_ids),
        ExamAttempt.id.in_(sub_official_id)
    )
    
    if exam_session_id:
        result_q = result_q.filter(ExamAttempt.exam_session_id == exam_session_id)
    if result_status:
        result_q = result_q.filter(ExamAttempt.result_status == result_status)
        
    result_q = result_q.order_by(
        ExamAttempt.score.desc(),
        ExamAttempt.correct_count.desc(),
        ExamAttempt.submitted_time.is_(None).asc(),
        ExamAttempt.submitted_time.asc(),
        Candidate.application_number.asc()
    )
    
    rows = result_q.all()
    export_data = format_export_rows(rows)
    
    df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=[
        "Application ID", "Applicant Name", "Department",
        "Programme Offered", "Subject", "Category", "Score",
        "Correct", "Wrong", "Unanswered", "Qualified Status", "Submission Type",
        "Login Time", "Submitted Time", "Time Taken", "System IP"
    ])
    
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Department Result")
        ws = writer.sheets["Department Result"]
        ws.protection.sheet = True
        ws.protection.password = "MCA2026"
    return out.getvalue()


def export_department_wise_details_excel(db: Session, exam_session_id: Optional[int] = None) -> bytes:
    """
    Phase 18: Generates a single Excel workbook containing worksheets for each active department.
    Each sheet contains the candidate results for that department, respecting the exam session filter,
    with the 16 standard columns.
    """
    departments = db.query(Department).filter(Department.is_active == True).order_by(Department.department_name).all()
    sub_official_id = get_official_attempts_subquery(db)
    
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer:
        for dept in departments:
            reg_ids = _get_session_candidate_ids(db, exam_session_id, department_id=dept.id)
            
            result_q = db.query(ExamAttempt, Candidate, Department).join(
                Candidate, ExamAttempt.candidate_id == Candidate.id
            ).join(
                Department, Candidate.department_id == Department.id
            ).filter(
                Candidate.is_active == True,
                ExamAttempt.candidate_id.in_(reg_ids),
                ExamAttempt.id.in_(sub_official_id)
            )
            
            if exam_session_id:
                result_q = result_q.filter(ExamAttempt.exam_session_id == exam_session_id)
                
            result_q = result_q.order_by(
                ExamAttempt.score.desc(),
                ExamAttempt.correct_count.desc(),
                ExamAttempt.submitted_time.is_(None).asc(),
                ExamAttempt.submitted_time.asc(),
                Candidate.application_number.asc()
            )
            
            rows = result_q.all()
            export_data = format_export_rows(rows)
            
            df = pd.DataFrame(export_data) if export_data else pd.DataFrame(columns=[
                "Application ID", "Applicant Name", "Department",
                "Programme Offered", "Subject", "Category", "Score",
                "Correct", "Wrong", "Unanswered", "Qualified Status", "Submission Type",
                "Login Time", "Submitted Time", "Time Taken", "System IP"
            ])
            
            sheet_name = dept.department_name[:30]
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            ws.protection.sheet = True
            ws.protection.password = "MCA2026"
            
    return out.getvalue()


def export_overall_result_pdf(
    db: Session,
    exam_session_id: Optional[int] = None,
    department_id: Optional[int] = None,
    result_status: Optional[str] = None
) -> bytes:
    from reportlab.lib.pagesizes import letter, landscape
    
    result_status = _map_result_status_filter(result_status)
    data = get_overall_result(db, exam_session_id, department_id, result_status, page=1, limit=100000)
    summary = data["summary"]
    rows = data["results"]
    
    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(letter),
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1e3a8a')
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#0f766e'), spaceBefore=10, spaceAfter=5
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155')
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white
    )
    
    story = []
    
    story.append(Paragraph("PhD Entrance Examination - Overall Results Report", title_style))
    story.append(Spacer(1, 10))
    
    data_summary = [
        [
            Paragraph("<b>Total Registered</b>", body_style),
            Paragraph("<b>Appeared</b>", body_style),
            Paragraph("<b>Absent</b>", body_style),
            Paragraph("<b>Qualified</b>", body_style),
            Paragraph("<b>Not Qualified</b>", body_style),
            Paragraph("<b>Qualified %</b>", body_style),
            Paragraph("<b>Avg Score</b>", body_style),
            Paragraph("<b>Lowest Score</b>", body_style),
            Paragraph("<b>Highest Score</b>", body_style)
        ],
        [
            Paragraph(str(summary["total_registered"]), body_style),
            Paragraph(str(summary["appeared"]), body_style),
            Paragraph(str(summary["absent"]), body_style),
            Paragraph(f"<font color='#16a34a'><b>{summary['passed']}</b></font>", body_style),
            Paragraph(f"<font color='#dc2626'><b>{summary['failed']}</b></font>", body_style),
            Paragraph(f"<b>{summary['pass_percentage']}%</b>", body_style),
            Paragraph(str(summary["average_score"]), body_style),
            Paragraph(str(summary["lowest_score"]), body_style),
            Paragraph(str(summary["highest_score"]), body_style)
        ]
    ]
    t_summary = Table(data_summary, colWidths=[80] * 9)
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("Candidate Results List", section_style))
    
    headers = [
        Paragraph("Rank", header_style),
        Paragraph("Application ID", header_style),
        Paragraph("Applicant Name", header_style),
        Paragraph("Initial", header_style),
        Paragraph("Department", header_style),
        Paragraph("Programme Offered", header_style),
        Paragraph("Subject", header_style),
        Paragraph("Category (FT/PT)", header_style),
        Paragraph("Score", header_style),
        Paragraph("Qualified Status", header_style),
        Paragraph("Submitted Time", header_style)
    ]
    
    table_data = [headers]
    for r in rows:
        sub_time = r["submitted_time"][:16].replace("T", " ") if r["submitted_time"] else "N/A"
        result_color = '#15803d' if r["result_status"] in ('PASS', 'QUALIFIED') else '#b91c1c'
        qualified_status = _format_result_status_response(r["result_status"])
        
        table_data.append([
            Paragraph(str(r["rank"]), body_style),
            Paragraph(r["application_id"], body_style),
            Paragraph(r["applicant_name"], body_style),
            Paragraph(r["initial"] or "--", body_style),
            Paragraph(r["department_name"], body_style),
            Paragraph(r["programme_offered"] or "--", body_style),
            Paragraph(r["subject"] or "--", body_style),
            Paragraph(r["category_ft_pt"] or "--", body_style),
            Paragraph(f"<b>{r['score']}</b>/70", body_style),
            Paragraph(f"<font color='{result_color}'><b>{qualified_status}</b></font>", body_style),
            Paragraph(sub_time, body_style)
        ])
        
    col_widths = [30, 80, 100, 35, 110, 85, 85, 65, 40, 60, 70]
    
    t_results = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_results.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t_results)
    
    doc.build(story)
    return out.getvalue()


def export_department_wise_pdf(db: Session, exam_session_id: Optional[int] = None) -> bytes:
    from reportlab.lib.pagesizes import letter, landscape
    
    data = get_department_wise_report(db, exam_session_id)
    departments = data["departments"]
    
    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(letter),
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1e3a8a')
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155')
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white
    )
    
    story = []
    
    story.append(Paragraph("PhD Entrance Examination - Department-wise Summary Report", title_style))
    story.append(Spacer(1, 15))
    
    headers = [
        Paragraph("S.No", header_style),
        Paragraph("Department", header_style),
        Paragraph("Registered", header_style),
        Paragraph("Appeared", header_style),
        Paragraph("Absent", header_style),
        Paragraph("Qualified", header_style),
        Paragraph("Not Qualified", header_style),
        Paragraph("Qualified %", header_style),
        Paragraph("Avg Score", header_style),
        Paragraph("Lowest Score", header_style),
        Paragraph("Highest Score", header_style),
        Paragraph("Question Bank Status", header_style)
    ]
    
    table_data = [headers]
    for idx, d in enumerate(departments):
        table_data.append([
            Paragraph(str(idx + 1), body_style),
            Paragraph(d["department_name"], body_style),
            Paragraph(str(d["registered"]), body_style),
            Paragraph(str(d["appeared"]), body_style),
            Paragraph(str(d["absent"]), body_style),
            Paragraph(f"<font color='#16a34a'><b>{d['passed']}</b></font>", body_style),
            Paragraph(f"<font color='#dc2626'><b>{d['failed']}</b></font>", body_style),
            Paragraph(f"{d['pass_percentage']}%" if d["appeared"] > 0 else "--", body_style),
            Paragraph(str(d["average_score"]) if d["appeared"] > 0 else "--", body_style),
            Paragraph(str(d["lowest_score"]) if d["appeared"] > 0 else "--", body_style),
            Paragraph(str(d["highest_score"]) if d["appeared"] > 0 else "--", body_style),
            Paragraph(d["question_bank_status"], body_style)
        ])
        
    col_widths = [30, 180, 50, 50, 50, 50, 50, 45, 50, 45, 45, 75]
    
    t_summary = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0f766e')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t_summary)
    
    doc.build(story)
    return out.getvalue()


def export_department_report_pdf(
    db: Session,
    department_id: int,
    exam_session_id: Optional[int] = None,
    result_status: Optional[str] = None
) -> bytes:
    from reportlab.lib.pagesizes import letter, landscape
    
    result_status = _map_result_status_filter(result_status)
    data = get_department_detail(db, department_id, exam_session_id, result_status)
    dept_name = data["department"]["name"]
    summary = data["summary"]
    rows = data["results"]
    
    out = BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=landscape(letter),
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor('#1e3a8a')
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor('#0f766e'), spaceBefore=10, spaceAfter=5
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155')
    )
    header_style = ParagraphStyle(
        'Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white
    )
    
    story = []
    
    story.append(Paragraph(f"PhD Entrance Examination - Department Report: {dept_name}", title_style))
    story.append(Spacer(1, 10))
    
    # Summary Table
    data_summary = [
        [
            Paragraph("<b>Registered</b>", body_style),
            Paragraph("<b>Appeared</b>", body_style),
            Paragraph("<b>Absent</b>", body_style),
            Paragraph("<b>Qualified</b>", body_style),
            Paragraph("<b>Not Qualified</b>", body_style),
            Paragraph("<b>Qualified %</b>", body_style),
            Paragraph("<b>Avg Score</b>", body_style),
            Paragraph("<b>Lowest Score</b>", body_style),
            Paragraph("<b>Highest Score</b>", body_style)
        ],
        [
            Paragraph(str(summary["registered"]), body_style),
            Paragraph(str(summary["appeared"]), body_style),
            Paragraph(str(summary["absent"]), body_style),
            Paragraph(f"<font color='#16a34a'><b>{summary['passed']}</b></font>", body_style),
            Paragraph(f"<font color='#dc2626'><b>{summary['failed']}</b></font>", body_style),
            Paragraph(f"<b>{summary['pass_percentage']}%</b>", body_style),
            Paragraph(str(summary["average_score"]), body_style),
            Paragraph(str(summary["lowest_score"]), body_style),
            Paragraph(str(summary["highest_score"]), body_style)
        ]
    ]
    t_summary = Table(data_summary, colWidths=[80] * 9)
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("Candidate Results List", section_style))
    
    headers = [
        Paragraph("Rank", header_style),
        Paragraph("Application ID", header_style),
        Paragraph("Applicant Name", header_style),
        Paragraph("Initial", header_style),
        Paragraph("Department", header_style),
        Paragraph("Programme Offered", header_style),
        Paragraph("Subject", header_style),
        Paragraph("Category (FT/PT)", header_style),
        Paragraph("Score", header_style),
        Paragraph("Qualified Status", header_style),
        Paragraph("Submitted Time", header_style)
    ]
    
    table_data = [headers]
    for r in rows:
        sub_time = r["submitted_time"][:16].replace("T", " ") if r["submitted_time"] else "N/A"
        result_color = '#15803d' if r["result_status"] in ('PASS', 'QUALIFIED') else '#b91c1c'
        qualified_status = _format_result_status_response(r["result_status"])
        
        table_data.append([
            Paragraph(str(r["rank"]), body_style),
            Paragraph(r["application_id"], body_style),
            Paragraph(r["applicant_name"], body_style),
            Paragraph(r["initial"] or "--", body_style),
            Paragraph(dept_name, body_style),
            Paragraph(r["programme_offered"] or "--", body_style),
            Paragraph(r["subject"] or "--", body_style),
            Paragraph(r["category_ft_pt"] or "--", body_style),
            Paragraph(f"<b>{r['score']}</b>/70", body_style),
            Paragraph(f"<font color='{result_color}'><b>{qualified_status}</b></font>", body_style),
            Paragraph(sub_time, body_style)
        ])
        
    col_widths = [30, 80, 100, 35, 110, 85, 85, 65, 40, 60, 70]
    
    t_results = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_results.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(t_results)
    
    doc.build(story)
    return out.getvalue()

