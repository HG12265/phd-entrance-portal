import os
import sys
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import SessionLocal
from app.models.admin import AdminUser
from app.models.department import Department
from app.models.exam_session import ExamSession
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer
from app.models.exam_attempt_reopen_audit import ExamAttemptReopenAudit

client = TestClient(app)
kolkata_tz = ZoneInfo("Asia/Kolkata")

def test_force_reopen():
    print("====================================================")
    print("          PHASE 14 - FORCE REOPEN INTEGRATION TEST  ")
    print("====================================================")
    
    db = SessionLocal()
    
    # 0. Clean leftover records
    leftover_dept = db.query(Department).filter(Department.department_code == "QARD").first()
    if leftover_dept:
        cand_ids = [c.id for c in db.query(Candidate.id).filter(Candidate.department_id == leftover_dept.id).all()]
        if cand_ids:
            db.query(ExamAttemptReopenAudit).filter(ExamAttemptReopenAudit.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(CandidateAnswer).filter(CandidateAnswer.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(Candidate).filter(Candidate.id.in_(cand_ids)).delete(synchronize_session=False)
        db.query(Question).filter(Question.department_id == leftover_dept.id).delete(synchronize_session=False)
        db.query(Department).filter(Department.id == leftover_dept.id).delete(synchronize_session=False)
        db.commit()

    leftover_sess = db.query(ExamSession).filter(ExamSession.session_name == "QA Reopen Session").first()
    if leftover_sess:
        db.query(Candidate).filter(Candidate.exam_session_id == leftover_sess.id).delete(synchronize_session=False)
        db.query(ExamSession).filter(ExamSession.id == leftover_sess.id).delete(synchronize_session=False)
        db.commit()
    
    # 1. Setup mock records
    dept = Department(department_name="QA-REOPEN-DEPT", department_code="QARD", description="Test", is_active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    
    # Add 70 mock questions
    for i in range(1, 71):
        q = Question(
            department_id=dept.id,
            question_no=i,
            question_text=f"Question text {i}",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_option="B", marks=1, is_active=True
        )
        db.add(q)
    db.commit()
    
    question = db.query(Question).filter(Question.department_id == dept.id, Question.question_no == 1).first()
    
    # Create ExamSession (Live)
    sess = ExamSession(
        session_name="QA Reopen Session",
        exam_title="QA Reopen Exam",
        exam_date=date.today(),
        start_time=datetime.now() - timedelta(minutes=10),
        end_time=datetime.now() + timedelta(minutes=80),
        duration_minutes=90,
        is_active=True
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    
    # Create Candidate
    cand = Candidate(
        application_number="QA/PHD/J26/9999",
        application_id="CETPHD-J26-9999",
        name="Test Candidate Reopen",
        dob=date(2000, 8, 15),
        applied_subject="Chemistry",
        department_id=dept.id,
        exam_session_id=sess.id,
        is_active=True
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    
    # Create Admin User if not exist
    admin = db.query(AdminUser).filter(AdminUser.email == "reopen_admin@example.com").first()
    if not admin:
        import bcrypt
        hashed_password = bcrypt.hashpw("adminpassword".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        admin = AdminUser(name="Reopen Admin", email="reopen_admin@example.com", password_hash=hashed_password, role="super_admin")
        db.add(admin)
        db.commit()
        db.refresh(admin)

    q_id = question.id
    db.close()
    
    try:
        # Get Candidate Token
        cand_login = client.post("/api/candidate/auth/login", json={
            "application_number": "QA/PHD/J26/9999",
            "dob": "15-08-2000"
        })
        assert cand_login.status_code == 200
        cand_token = cand_login.json().get("access_token")
        cand_headers = {"Authorization": f"Bearer {cand_token}", "X-Exam-Client-Id": "qa-reopen-fingerprint"}
        
        # Get Admin Token
        admin_login = client.post("/api/admin/auth/login", json={
            "email": "reopen_admin@example.com",
            "password": "adminpassword"
        })
        assert admin_login.status_code == 200
        admin_token = admin_login.json().get("access_token")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Candidate enters exam
        enter_res = client.post("/api/candidate/exam/enter", headers=cand_headers)
        assert enter_res.status_code == 200
        
        # Start attempt
        start_res = client.post("/api/candidate/exam/start", headers=cand_headers)
        assert start_res.status_code == 200
        attempt_id = start_res.json().get("attempt_id")
        
        # Save an answer
        save_res = client.post("/api/candidate/exam/save-answer", json={
            "attempt_id": attempt_id,
            "question_id": q_id,
            "selected_option": "B",
            "answer_status": "answered"
        }, headers=cand_headers)
        print("Save res status:", save_res.status_code, "body:", save_res.text)
        assert save_res.status_code == 200
        
        # Submit exam attempt
        submit_res = client.post("/api/candidate/exam/submit", json={
            "attempt_id": attempt_id,
            "submission_type": "manual"
        }, headers=cand_headers)
        assert submit_res.status_code == 200
        assert submit_res.json().get("status") == "submitted"
        assert submit_res.json().get("score") == 1
        
        # Admin Searches Candidate by application_id (case-insensitive, spaces trimmed)
        search_res = client.get("/api/admin/exam-control/candidate/  cetphd-j26-9999  ", headers=admin_headers)
        assert search_res.status_code == 200
        assert search_res.json().get("attempt").get("status") == "submitted"
        
        # Admin Force Reopens the Submitted Exam
        reopen_res = client.post("/api/admin/exam-control/force-reopen-submitted", json={
            "application_number": "QA/PHD/J26/9999",
            "reason": "Test accidental submission override",
            "confirm_text": "REOPEN",
            "extra_minutes": None
        }, headers=admin_headers)
        assert reopen_res.status_code == 200
        assert reopen_res.json().get("submitted_reopen_count") == 1
        
        # Verify attempt properties in DB
        db = SessionLocal()
        db_attempt = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
        assert db_attempt.status == "in_progress"
        assert db_attempt.score == 0
        assert db_attempt.submitted_time is None
        assert db_attempt.reopened_from_submitted is True
        
        # Verify CandidateAnswer was reset
        db_answer = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt_id, CandidateAnswer.question_id == q_id).first()
        assert db_answer.is_correct is None
        assert db_answer.mark_awarded == 0
        
        # Verify Reopen Audit was created
        db_audit = db.query(ExamAttemptReopenAudit).filter(ExamAttemptReopenAudit.attempt_id == attempt_id).first()
        assert db_audit is not None
        assert db_audit.reopen_type == "submitted_force_reopen"
        assert db_audit.old_status == "submitted"
        assert db_audit.old_score == 1
        assert db_audit.reason == "Test accidental submission override"
        print("[PASSED] Database attributes and Reopen audit validation.")
        
        # Candidate checks result API -> should reject with HTTP 400 Reopened error
        result_res = client.get("/api/candidate/exam/result", headers=cand_headers)
        assert result_res.status_code == 400
        assert "is currently reopened/in progress" in result_res.json().get("detail")
        print("[PASSED] Result page block validation.")
        
        # Candidate resumes and submits again
        submit_again = client.post("/api/candidate/exam/submit", json={
            "attempt_id": attempt_id,
            "submission_type": "manual"
        }, headers=cand_headers)
        assert submit_again.status_code == 200
        assert submit_again.json().get("status") == "submitted"
        assert submit_again.json().get("score") == 1
        
        # Clean up database test entries
        db.query(ExamAttemptReopenAudit).filter(ExamAttemptReopenAudit.attempt_id == attempt_id).delete()
        db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == attempt_id).delete()
        db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).delete()
        db.query(Candidate).filter(Candidate.id == cand.id).delete()
        db.query(ExamSession).filter(ExamSession.id == sess.id).delete()
        db.query(Question).filter(Question.department_id == dept.id).delete()
        db.query(Department).filter(Department.id == dept.id).delete()
        db.commit()
        db.close()
        
        print("[PASSED] Phase 14 Force Reopen test suite completed successfully.")
        
    except AssertionError as e:
        print(f"[FAILED] Phase 14 Force Reopen validation failed: {e}")
        # Clean up database on fail
        db = SessionLocal()
        qard_dept = db.query(Department).filter(Department.department_code == "QARD").first()
        if qard_dept:
            cand_ids = [c.id for c in db.query(Candidate.id).filter(Candidate.department_id == qard_dept.id).all()]
            if cand_ids:
                db.query(ExamAttemptReopenAudit).filter(ExamAttemptReopenAudit.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
                db.query(CandidateAnswer).filter(CandidateAnswer.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
                db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
                db.query(Candidate).filter(Candidate.id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.department_id == qard_dept.id).delete(synchronize_session=False)
            db.query(Department).filter(Department.id == qard_dept.id).delete(synchronize_session=False)
        
        qard_sess = db.query(ExamSession).filter(ExamSession.session_name == "QA Reopen Session").first()
        if qard_sess:
            db.query(Candidate).filter(Candidate.exam_session_id == qard_sess.id).delete(synchronize_session=False)
            db.query(ExamSession).filter(ExamSession.id == qard_sess.id).delete(synchronize_session=False)
        db.commit()
        db.close()
        raise e

if __name__ == "__main__":
    test_force_reopen()
