import os
import io
import zipfile
import json
from datetime import datetime, date
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text
from zoneinfo import ZoneInfo

from app.config import UPLOAD_DIR
from app.models import (
    Candidate,
    ExamSession,
    Question,
    ExamAttempt,
    CandidateAnswer,
    Department,
    AdminUser,
    ExamAttemptReopenAudit,
    ImportLog,
    SystemSetting
)

kolkata_tz = ZoneInfo("Asia/Kolkata")

def sql_quote(val):
    if val is None:
        return "NULL"
    elif isinstance(val, bool):
        return "1" if val else "0"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    else:
        # Escape backslashes and single quotes
        s = str(val).replace("\\", "\\\\").replace("'", "''").replace("\0", "")
        return f"'{s}'"

def generate_database_sql_dump(db: Session) -> str:
    """Generates clean SQL dump statements for all database tables."""
    lines = [
        "-- PHD ENTRANCE PORTAL COMPLETE DATABASE DUMP",
        f"-- Generated At: {datetime.now(kolkata_tz).strftime('%Y-%m-%d %H:%M:%S IST')}",
        "SET FOREIGN_KEY_CHECKS = 0;\n"
    ]

    tables = [
        "system_settings",
        "admin_users",
        "departments",
        "exam_sessions",
        "candidates",
        "questions",
        "exam_attempts",
        "candidate_answers",
        "exam_attempt_reopen_audits",
        "import_logs"
    ]

    for table_name in tables:
        try:
            result = db.execute(text(f"SELECT * FROM `{table_name}`"))
            rows = result.fetchall()
            keys = list(result.keys())

            if not keys:
                continue

            lines.append(f"-- --------------------------------------------------------")
            lines.append(f"-- Table structure and data for {table_name}")
            lines.append(f"-- --------------------------------------------------------")

            cols_str = ", ".join([f"`{k}`" for k in keys])

            for row in rows:
                row_dict = dict(zip(keys, row))
                val_strs = [sql_quote(row_dict[k]) for k in keys]
                vals_joined = ", ".join(val_strs)
                lines.append(f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({vals_joined});")

            lines.append("")
        except Exception as err:
            lines.append(f"-- Error dumping table {table_name}: {err}\n")

    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    return "\n".join(lines)


def generate_excel_bytes(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """Helper to convert a pandas DataFrame into Excel bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


def create_full_backup_zip(db: Session) -> io.BytesIO:
    """
    Generates a complete ZIP archive containing:
    1. database_dump.sql
    2. excel_reports/ (candidate_list.xlsx, exam_sessions.xlsx, question_banks.xlsx, exam_results_reports.xlsx)
    3. candidate_photos/ (all candidate photos)
    4. question_images/ (all question images)
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Add SQL database dump
        sql_content = generate_database_sql_dump(db)
        zip_file.writestr("database_dump.sql", sql_content)

        # 2. Add Excel Reports
        # a) Candidate List
        candidates = db.query(Candidate).all()
        cand_data = []
        for c in candidates:
            cand_data.append({
                "ID": c.id,
                "Application Number": getattr(c, "application_number", ""),
                "Application ID": getattr(c, "application_id", ""),
                "Name": getattr(c, "name", ""),
                "DOB": c.dob.strftime('%Y-%m-%d') if getattr(c, "dob", None) else "",
                "Department": c.department.department_name if getattr(c, "department", None) else "",
                "Mobile Number": getattr(c, "mobile_number", ""),
                "Email": getattr(c, "email", ""),
                "Applied Subject": getattr(c, "applied_subject", ""),
                "Category (FT/PT)": getattr(c, "category_ft_pt", ""),
                "Photo Status": getattr(c, "photo_status", "missing"),
                "Is Active": "Yes" if getattr(c, "is_active", True) else "No",
                "Created At": c.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(c, "created_at", None) else ""
            })
        df_cand = pd.DataFrame(cand_data if cand_data else [{"Message": "No candidates found"}])
        zip_file.writestr("excel_reports/candidate_list.xlsx", generate_excel_bytes(df_cand, "Candidates"))

        # b) Exam Sessions
        sessions = db.query(ExamSession).all()
        sess_data = []
        for s in sessions:
            sess_data.append({
                "Session ID": s.id,
                "Session Name": getattr(s, "session_name", ""),
                "Exam Title": getattr(s, "exam_title", ""),
                "Start Time": s.start_time.strftime('%Y-%m-%d %H:%M:%S') if getattr(s, "start_time", None) else "",
                "End Time": s.end_time.strftime('%Y-%m-%d %H:%M:%S') if getattr(s, "end_time", None) else "",
                "Duration Mins": getattr(s, "duration_minutes", 0),
                "Instructions": getattr(s, "instructions", ""),
                "Is Active": "Yes" if getattr(s, "is_active", True) else "No"
            })
        df_sess = pd.DataFrame(sess_data if sess_data else [{"Message": "No exam sessions found"}])
        zip_file.writestr("excel_reports/exam_sessions.xlsx", generate_excel_bytes(df_sess, "Sessions"))

        # c) Question Banks
        questions = db.query(Question).all()
        q_data = []
        for q in questions:
            q_data.append({
                "Question ID": q.id,
                "Department": q.department.department_name if getattr(q, "department", None) else "",
                "Question No": getattr(q, "question_no", 0),
                "Question Text": getattr(q, "question_text", ""),
                "Option A": getattr(q, "option_a", ""),
                "Option B": getattr(q, "option_b", ""),
                "Option C": getattr(q, "option_c", ""),
                "Option D": getattr(q, "option_d", ""),
                "Correct Answer": getattr(q, "correct_option", ""),
                "Marks": getattr(q, "marks", 1),
                "Image Path": getattr(q, "image_path", "")
            })
        df_q = pd.DataFrame(q_data if q_data else [{"Message": "No questions found"}])
        zip_file.writestr("excel_reports/question_banks.xlsx", generate_excel_bytes(df_q, "Questions"))

        # d) Exam Results & Attempts Report
        attempts = db.query(ExamAttempt).all()
        att_data = []
        for a in attempts:
            cand = a.candidate
            att_data.append({
                "Attempt ID": a.id,
                "Candidate Name": cand.name if cand else "",
                "Application Number": cand.application_number if cand else "",
                "Department": cand.department.department_name if cand and getattr(cand, "department", None) else "",
                "Status": getattr(a, "status", ""),
                "Score": getattr(a, "score", 0),
                "Total Questions": getattr(a, "total_questions", 70),
                "Correct Count": getattr(a, "correct_count", 0),
                "Wrong Count": getattr(a, "wrong_count", 0),
                "Unanswered Count": getattr(a, "unanswered_count", 0),
                "Result Status": getattr(a, "result_status", ""),
                "Start Time": a.start_time.strftime('%Y-%m-%d %H:%M:%S') if getattr(a, "start_time", None) else "",
                "Submitted Time": a.submitted_time.strftime('%Y-%m-%d %H:%M:%S') if getattr(a, "submitted_time", None) else ""
            })
        df_att = pd.DataFrame(att_data if att_data else [{"Message": "No exam attempts found"}])
        zip_file.writestr("excel_reports/exam_results_reports.xlsx", generate_excel_bytes(df_att, "Results"))

        # 3. Add Candidate Photos
        base_upload = os.path.abspath(UPLOAD_DIR)
        photos_dir = os.path.join(base_upload, "candidate_photos")
        if os.path.exists(photos_dir):
            for filename in os.listdir(photos_dir):
                file_path = os.path.join(photos_dir, filename)
                if os.path.isfile(file_path):
                    zip_file.write(file_path, arcname=f"candidate_photos/{filename}")

        # 4. Add Question Images
        q_img_dir = os.path.join(base_upload, "question_images")
        if os.path.exists(q_img_dir):
            for filename in os.listdir(q_img_dir):
                file_path = os.path.join(q_img_dir, filename)
                if os.path.isfile(file_path):
                    zip_file.write(file_path, arcname=f"question_images/{filename}")

    zip_buffer.seek(0)
    return zip_buffer
