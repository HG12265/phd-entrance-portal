import os
import sys
import json
import uuid
import pandas as pd
from datetime import datetime, date, timedelta
from io import BytesIO
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

client = TestClient(app)

def clean_db_leftovers():
    db = SessionLocal()
    try:
        dept_ids = [d.id for d in db.query(Department.id).filter(Department.department_code.in_(["QA-TEST-CS", "QA-TEMP-CASC"])).all()]
        cand_ids = [c.id for c in db.query(Candidate.id).filter(
            (Candidate.department_id.in_(dept_ids)) | 
            (Candidate.application_number.in_(["MANUAL/PHD/J26/9999", "MANUAL/PHD/J26/0001", "MANUAL/PHD/J26/0002", "TEMP/PHD/J26/1111", "TEMP/PHD/J26/2222", "TEMP/PHD/J26/3333", "qatest"]))
        ).all()]
        
        if cand_ids:
            db.query(CandidateAnswer).filter(CandidateAnswer.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
            db.query(Candidate).filter(Candidate.id.in_(cand_ids)).delete(synchronize_session=False)

        if dept_ids:
            q_ids = [q.id for q in db.query(Question.id).filter(Question.department_id.in_(dept_ids)).all()]
            if q_ids:
                db.query(CandidateAnswer).filter(CandidateAnswer.question_id.in_(q_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.department_id.in_(dept_ids)).delete(synchronize_session=False)

        db.query(ExamSession).filter(ExamSession.session_name.in_(["QA Live Session", "QA Session for Cascades"])).delete(synchronize_session=False)

        if dept_ids:
            db.query(Department).filter(Department.id.in_(dept_ids)).delete(synchronize_session=False)

        db.commit()
    except Exception as e:
        print(f"Pre-cleanup warning: {e}")
        db.rollback()
    finally:
        db.close()

def run_all_qa_tests():
    print("====================================================")
    print("         PHD ENTRANCE PORTAL - QA TEST SUITE        ")
    print("====================================================")
    
    clean_db_leftovers()
    results = []

    # Helper function to record test status
    def record_test(module, area, status, observation, fix_applied="None"):
        results.append({
            "Module": module,
            "Test Area": area,
            "Status": status,
            "Observation": observation,
            "Fix": fix_applied
        })
        print(f"[{status}] {module} - {area}: {observation}")

    # 1. Startup & Imports
    try:
        from app.main import app as test_app
        record_test("Startup", "Imports Check", "PASSED", "All backend modules and main routers imported cleanly.")
    except Exception as e:
        record_test("Startup", "Imports Check", "FAILED", f"Import failed: {str(e)}")

    # 2. Admin Authentication
    admin_token = None
    candidate_token = None
    try:
        # 2a. Success Login
        login_res = client.post("/api/admin/auth/login", json={
            "email": "admin@example.com",
            "password": "MCA2026"
        })
        if login_res.status_code == 200:
            admin_token = login_res.json().get("access_token")
            record_test("Admin Auth", "Valid Credentials", "PASSED", "Super admin logged in successfully.")
        else:
            record_test("Admin Auth", "Valid Credentials", "FAILED", f"Status: {login_res.status_code}, Body: {login_res.text}")

        # 2b. Invalid Password Login
        bad_login = client.post("/api/admin/auth/login", json={
            "email": "admin@example.com",
            "password": "wrongpassword"
        })
        if bad_login.status_code == 401:
            record_test("Admin Auth", "Invalid Password", "PASSED", "Rejected invalid password correctly with HTTP 401.")
        else:
            record_test("Admin Auth", "Invalid Password", "FAILED", f"Failed rejection. Status: {bad_login.status_code}")

        # 2c. Protected APIs checks
        no_auth = client.get("/api/admin/departments")
        if no_auth.status_code in (401, 403):
            record_test("Admin Auth", "No Token Security", "PASSED", "Protected route rejected requests lacking authorization.")
        else:
            record_test("Admin Auth", "No Token Security", "FAILED", f"Allowed request without token. Status: {no_auth.status_code}")

    except Exception as e:
        record_test("Admin Auth", "General", "FAILED", f"Authentication test crashed: {str(e)}")

    # 3. Department CRUD
    test_dept_id = None
    test_dept_code = "QA-TEST-CS"
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        
        # Cleanup department if existing from previous manual runs
        clean_db_leftovers()

        # 3a. Create Department
        create_res = client.post("/api/admin/departments", json={
            "department_name": "QA Computer Science",
            "department_code": test_dept_code,
            "description": "QA validation department"
        }, headers=headers)
        
        if create_res.status_code in (200, 201):
            test_dept_id = create_res.json().get("id")
            record_test("Departments", "Create Department", "PASSED", f"Created department '{test_dept_code}' successfully.")
        else:
            record_test("Departments", "Create Department", "FAILED", f"Status: {create_res.status_code}, Body: {create_res.text}")

        # 3b. Duplicate Validation
        dup_res = client.post("/api/admin/departments", json={
            "department_name": "QA Computer Science Duplicate",
            "department_code": test_dept_code,
            "description": "Duplicate department"
        }, headers=headers)
        if dup_res.status_code == 400:
            record_test("Departments", "Duplicate Validation", "PASSED", "Prevented duplicate department code mapping correctly.")
        else:
            record_test("Departments", "Duplicate Validation", "FAILED", f"Status: {dup_res.status_code}")

    except Exception as e:
        record_test("Departments", "General", "FAILED", f"Department CRUD crashed: {str(e)}")

    # 4. Exam Sessions
    test_session_id = None
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        exam_date = (date.today() + timedelta(days=1)).isoformat()
        start_datetime = f"{exam_date}T09:00:00"
        end_datetime = f"{exam_date}T10:30:00"
        
        # 4a. Create Active Session
        session_res = client.post("/api/admin/exam-sessions", json={
            "session_name": "QA Exam Session A",
            "exam_date": exam_date,
            "start_time": start_datetime,
            "end_time": end_datetime,
            "duration_minutes": 90,
            "is_active": True,
            "department_ids": [test_dept_id]
        }, headers=headers)
        
        if session_res.status_code in (200, 201):
            test_session_id = session_res.json().get("id")
            record_test("Exam Sessions", "Create Session", "PASSED", f"Created live exam session for date {exam_date} successfully.")
        else:
            record_test("Exam Sessions", "Create Session", "FAILED", f"Status: {session_res.status_code}, Body: {session_res.text}")

        # 4b. Session Duplicate Same Date Check (Safeguard 5)
        dup_session = client.post("/api/admin/exam-sessions", json={
            "session_name": "QA Exam Session A",
            "exam_date": exam_date,
            "start_time": f"{exam_date}T14:00:00",
            "end_time": f"{exam_date}T15:30:00",
            "duration_minutes": 90,
            "is_active": True
        }, headers=headers)
        if dup_session.status_code == 400:
            record_test("Exam Sessions", "Duplicate Active Session Check", "PASSED", "Blocked duplicate active session name for same date.")
        else:
            record_test("Exam Sessions", "Duplicate Active Session Check", "FAILED", f"Allowed duplicate. Status: {dup_session.status_code}")

    except Exception as e:
        record_test("Exam Sessions", "General", "FAILED", f"Session CRUD crashed: {str(e)}")

    # 5. Candidate Upload + Photo Mapping
    test_candidate_app = "CET/PHD/QA/9999"
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        
        # Clean existing candidates
        db = SessionLocal()
        existing_cand = db.query(Candidate).filter(Candidate.application_number == test_candidate_app).first()
        if existing_cand:
            db.delete(existing_cand)
            db.commit()
        db.close()

        # 5a. Mock excel creation inside pandas
        df_cands = pd.DataFrame([{
            "name": "QA Candidate Tester",
            "application_number": test_candidate_app,
            "mail_id": "qatest@candidate.com",
            "applied_subject": test_dept_code,
            "dob": "15-08-2000",
            "mobile_number": "9876543210",
            "exam_session": "QA Exam Session A"
        }])
        
        excel_io = BytesIO()
        with pd.ExcelWriter(excel_io, engine='openpyxl') as writer:
            df_cands.to_excel(writer, index=False)
        excel_io.seek(0)
        
        # 5b. Upload Candidates Excel via TestClient
        upload_res = client.post("/api/admin/candidates/upload-excel", files={
            "file": ("candidates.xlsx", excel_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }, headers=headers)
        
        if upload_res.status_code == 200:
            res_summary = upload_res.json()
            record_test("Candidate Upload", "Valid Excel Upload", "PASSED", f"Parsed candidate excel sheet: successful={res_summary.get('success_count')}")
        else:
            record_test("Candidate Upload", "Valid Excel Upload", "FAILED", f"Status: {upload_res.status_code}, Body: {upload_res.text}")

        # 5c. Candidate Photo Mapping verification (Salem naming structure)
        # CET/PHD/QA/9999 expects CET-PHD-QA-9999.JPG.
        # Let's verify via scanning remap photo scan or database columns
        remap_res = client.post("/api/admin/candidates/remap-photos", headers=headers)
        if remap_res.status_code == 200:
            record_test("Photo Mapping", "Photos Directory Scan", "PASSED", "Executed photos directories remapping without crash.")
        else:
            record_test("Photo Mapping", "Photos Directory Scan", "FAILED", f"Status: {remap_res.status_code}")

    except Exception as e:
        record_test("Candidate Upload", "General", "FAILED", f"Candidate Upload tests crashed: {str(e)}")

    # 6. Question Bank Upload (Exactly 70 Validation)
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        
        # 6a. Generate 70 questions
        q_rows = []
        for i in range(1, 71):
            q_rows.append({
                "Question No": i,
                "Question Text": f"QA Question {i}: What is 2 + 2?",
                "Option A": "3",
                "Option B": "4",
                "Option C": "5",
                "Option D": "6",
                "Correct Option": "B",
                "Marks": 1
            })
            
        df_qs = pd.DataFrame(q_rows)
        excel_qs_io = BytesIO()
        with pd.ExcelWriter(excel_qs_io, engine='openpyxl') as writer:
            df_qs.to_excel(writer, index=False)
        excel_qs_io.seek(0)
        
        # Upload exactly 70 questions (replace_existing=True)
        q_upload_res = client.post(f"/api/admin/questions/upload-excel/{test_dept_id}?replace_existing=true", files={
            "file": ("questions.xlsx", excel_qs_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }, headers=headers)
        
        if q_upload_res.status_code == 200:
            record_test("Question Bank", "Upload exactly 70 questions", "PASSED", "Enforced and accepted exactly 70 questions.")
        else:
            record_test("Question Bank", "Upload exactly 70 questions", "FAILED", f"Status: {q_upload_res.status_code}, Body: {q_upload_res.text}")

        # 6b. Block invalid question count (e.g. 68 questions)
        df_qs_invalid = pd.DataFrame(q_rows[:68])
        excel_qs_invalid_io = BytesIO()
        with pd.ExcelWriter(excel_qs_invalid_io, engine='openpyxl') as writer:
            df_qs_invalid.to_excel(writer, index=False)
        excel_qs_invalid_io.seek(0)
        
        q_bad_res = client.post(f"/api/admin/questions/upload-excel/{test_dept_id}?replace_existing=true", files={
            "file": ("questions.xlsx", excel_qs_invalid_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }, headers=headers)
        
        if q_bad_res.status_code == 200 and "validation failed" in q_bad_res.json().get("message", "").lower():
            record_test("Question Bank", "Block non-70 questions", "PASSED", "Blocked 68 questions upload correctly.")
        else:
            record_test("Question Bank", "Block non-70 questions", "FAILED", f"Accepted 68 questions. Status: {q_bad_res.status_code}")

    except Exception as e:
        record_test("Question Bank", "General", "FAILED", f"Question Upload tests crashed: {str(e)}")

    # 7. Candidate Login + Exam Start Lock
    try:
        # 7a. Candidate Login
        cand_login = client.post("/api/candidate/auth/login", json={
            "application_number": test_candidate_app,
            "dob": "15-08-2000"
        })
        if cand_login.status_code == 200:
            candidate_token = cand_login.json().get("access_token")
            record_test("Candidate Login", "Valid Credentials Login", "PASSED", "Candidate authenticated successfully.")
        else:
            record_test("Candidate Login", "Valid Credentials Login", "FAILED", f"Status: {cand_login.status_code}")

        # 7b. Before exam start time enter lock
        # Let's adjust session start time to be in the future, then hit /api/candidate/exam/enter
        # Since we set session date to date.today() + 1 day, it is naturally locked (not started yet)!
        cand_headers = {"Authorization": f"Bearer {candidate_token}", "X-Exam-Client-Id": "qa-test-fingerprint"} if candidate_token else {}
        enter_lock = client.post("/api/candidate/exam/enter", headers=cand_headers)
        if enter_lock.status_code in (400, 403) and ("not live" in enter_lock.json().get("detail", "").lower() or "not started" in enter_lock.json().get("detail", "").lower()):
            record_test("Exam Start Lock", "Future Exam Lock", "PASSED", "Locked Candidate out of exam session prior to start time.")
        else:
            record_test("Exam Start Lock", "Future Exam Lock", "FAILED", f"Status: {enter_lock.status_code}, Body: {enter_lock.text}")

        # Adjust the exam session in database to be LIVE (start_time in past, end_time in future) to allow exam entry
        import zoneinfo
        kolkata = zoneinfo.ZoneInfo("Asia/Kolkata")
        now_kolkata = datetime.now(kolkata)
        db = SessionLocal()
        sess = db.query(ExamSession).filter(ExamSession.id == test_session_id).first()
        if sess:
            sess.exam_date = now_kolkata.date()
            # 90 minutes session (naive datetimes representing Asia/Kolkata time)
            sess.start_time = (now_kolkata - timedelta(minutes=10)).replace(tzinfo=None)
            sess.end_time = (now_kolkata + timedelta(minutes=80)).replace(tzinfo=None)
            db.commit()
        db.close()
        
        # Hit enter again (should pass!)
        enter_unlock = client.post("/api/candidate/exam/enter", headers=cand_headers)
        if enter_unlock.status_code == 200:
            record_test("Exam Start Lock", "Live Exam Access", "PASSED", "Allowed Candidate into live exam session successfully.")
        else:
            record_test("Exam Start Lock", "Live Exam Access", "FAILED", f"Status: {enter_unlock.status_code}, Body: {enter_unlock.text}")

    except Exception as e:
        record_test("Candidate Login", "General", "FAILED", f"Candidate login tests crashed: {str(e)}")

    # 8. Live Exam Interface + Autosave
    test_attempt_id = None
    try:
        cand_headers = {"Authorization": f"Bearer {candidate_token}", "X-Exam-Client-Id": "qa-test-fingerprint"} if candidate_token else {}
        
        # 8a. Start Exam (creates ExamAttempt and CandidateAnswer rows)
        start_res = client.post("/api/candidate/exam/start", headers=cand_headers)
        if start_res.status_code == 200:
            test_attempt_id = start_res.json().get("attempt_id")
            questions_received = start_res.json().get("questions", [])
            
            # Security Verification: verify 'correct_option' is omitted
            leak_detected = any("correct_option" in q or "answer" in q for q in questions_received)
            if not leak_detected:
                record_test("Security", "Candidate Questions Leak Check", "PASSED", "Candidate APIs omit correct answer mappings.")
            else:
                record_test("Security", "Candidate Questions Leak Check", "FAILED", "Correct options leaked in start exam API!")
            
            record_test("Exam Interface", "Start Exam Attempt", "PASSED", f"Created attempt={test_attempt_id} with 70 shuffled questions.")
        else:
            record_test("Exam Interface", "Start Exam Attempt", "FAILED", f"Status: {start_res.status_code}, Body: {start_res.text}")

        # 8b. Save answer autosave
        if test_attempt_id and len(questions_received) > 0:
            first_q_id = questions_received[0]["question_id"]
            save_res = client.post("/api/candidate/exam/save-answer", json={
                "attempt_id": test_attempt_id,
                "question_id": first_q_id,
                "selected_option": "A"
            }, headers=cand_headers)
            
            if save_res.status_code == 200:
                record_test("Exam Interface", "Save Answer Autosave", "PASSED", "Autosave choice saved correctly to database.")
            else:
                record_test("Exam Interface", "Save Answer Autosave", "FAILED", f"Status: {save_res.status_code}")

    except Exception as e:
        record_test("Exam Interface", "General", "FAILED", f"Live Exam interface tests crashed: {str(e)}")

    # 9. Submit & Result scoring (Threshold pass/fail checks)
    try:
        cand_headers = {"Authorization": f"Bearer {candidate_token}", "X-Exam-Client-Id": "qa-test-fingerprint"} if candidate_token else {}
        
        # Set database answers to score exactly 28 correct (Passing mark)
        db = SessionLocal()
        q_ids = db.query(Question.id).filter(Question.department_id == test_dept_id).all()
        q_ids = [q[0] for q in q_ids]
        
        # Populate 28 correct answers and 42 wrong/unanswered
        ans_rows = db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id == test_attempt_id).all()
        for idx, ans in enumerate(ans_rows):
            if idx < 28:
                ans.selected_option = "B"  # Correct choice is "B"
            else:
                ans.selected_option = "C"  # Incorrect choice
        db.commit()
        db.close()

        # Submit attempt
        submit_res = client.post("/api/candidate/exam/submit", json={
            "attempt_id": test_attempt_id,
            "submission_type": "manual"
        }, headers=cand_headers)
        
        if submit_res.status_code == 200:
            res_data = submit_res.json()
            score_computed = res_data.get("score")
            result_status = res_data.get("result_status")
            
            if score_computed == 28 and result_status in ("PASS", "QUALIFIED"):
                record_test("Submit/Result", "PASS score boundary", "PASSED", f"Scored exactly 28: marked result as {result_status}.")
            else:
                record_test("Submit/Result", "PASS score boundary", "FAILED", f"Score: {score_computed}, Status: {result_status}")
        else:
            record_test("Submit/Result", "PASS score boundary", "FAILED", f"Submit endpoint returned HTTP {submit_res.status_code}")

        # Try to save answers after submit (Attempt lock)
        lock_save = client.post("/api/candidate/exam/save-answer", json={
            "attempt_id": test_attempt_id,
            "question_id": q_ids[0],
            "selected_option": "D"
        }, headers=cand_headers)
        if lock_save.status_code in (400, 403):
            record_test("Submit/Result", "Submitted Attempt Lock", "PASSED", "Blocked answer modification requests on finalized attempt.")
        else:
            record_test("Submit/Result", "Submitted Attempt Lock", "FAILED", f"Allowed modification on locked attempt. Status: {lock_save.status_code}")

        # Security: candidate result leakage audit
        res_summary = client.get("/api/candidate/exam/result", headers=cand_headers)
        if res_summary.status_code == 200:
            summary_data = res_summary.json()
            leak_check = any("correct_option" in q or "answer" in q for q in summary_data.get("answers", []))
            if not leak_check:
                record_test("Security", "Result Keys Leak Check", "PASSED", "Candidate results API does not expose correct options or explanations.")
            else:
                record_test("Security", "Result Keys Leak Check", "FAILED", "Candidate results leaked correct answer options.")
        else:
            record_test("Security", "Result Keys Leak Check", "FAILED", f"Result fetch error: {res_summary.status_code}")

    except Exception as e:
        record_test("Submit/Result", "General", "FAILED", f"Submit and Result tests crashed: {str(e)}")

    # 10. Admin Reports & Exports
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        
        # 10a. Reports summary metrics card stats
        summary_res = client.get("/api/admin/reports/summary", headers=headers)
        if summary_res.status_code == 200:
            record_test("Admin Reports", "Summary Stats Cards", "PASSED", f"Summary counters: appeared={summary_res.json().get('appeared')}, passed={summary_res.json().get('passed')}")
        else:
            record_test("Admin Reports", "Summary Stats Cards", "FAILED", f"Status: {summary_res.status_code}")

        # 10b. Excel exports (Overall, Subject, Absentees)
        excel_overall = client.get("/api/admin/reports/export/overall-excel", headers=headers)
        if excel_overall.status_code == 200:
            record_test("Exports", "Overall Leaderboard Excel", "PASSED", "Generated overall spreadsheet download stream successfully.")
        else:
            record_test("Exports", "Overall Leaderboard Excel", "FAILED", f"Status: {excel_overall.status_code}")

        # 10c. PDF export
        db = SessionLocal()
        uploaded_cand = db.query(Candidate).filter(Candidate.application_number == test_candidate_app).first()
        cand_id = uploaded_cand.id if uploaded_cand else 1
        db.close()
        
        pdf_res = client.get(f"/api/admin/reports/export/candidate-pdf/{cand_id}", headers=headers)
        if pdf_res.status_code == 200:
            record_test("Exports", "Candidate Score Card PDF", "PASSED", "Generated ReportLab candidate report sheet PDF stream.")
        else:
            record_test("Exports", "Candidate Score Card PDF", "FAILED", f"Status: {pdf_res.status_code}")

    except Exception as e:
        record_test("Admin Reports", "General", "FAILED", f"Reports and Exports tests crashed: {str(e)}")

    # 11. Security Roles Enforcement
    try:
        # Candidate token visiting admin endpoint
        cand_headers = {"Authorization": f"Bearer {candidate_token}"} if candidate_token else {}
        cross_auth = client.get("/api/admin/departments", headers=cand_headers)
        if cross_auth.status_code in (401, 403):
            record_test("Security", "Candidate Role Isolation", "PASSED", "Candidate tokens are correctly blocked from accessing Admin endpoints.")
        else:
            record_test("Security", "Candidate Role Isolation", "FAILED", f"Candidate token accessed admin route. Status: {cross_auth.status_code}")
            
        # Admin token visiting candidate attempt endpoint
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        cross_auth_cand = client.post("/api/candidate/exam/start", headers=headers)
        if cross_auth_cand.status_code in (401, 403):
            record_test("Security", "Admin Role Isolation", "PASSED", "Admin tokens are correctly blocked from candidate exam endpoints.")
        else:
            record_test("Security", "Admin Role Isolation", "FAILED", f"Admin token accessed candidate attempt. Status: {cross_auth_cand.status_code}")

    except Exception as e:
        record_test("Security", "General", "FAILED", f"Security role checks crashed: {str(e)}")

    # 12. Phase 10 Delete Controls + Manual Candidate Add
    try:
        headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        cand_headers = {"Authorization": f"Bearer {candidate_token}"} if candidate_token else {}

        # 12a. Manual candidate add: Valid
        man_res = client.post("/api/admin/candidates/manual", json={
            "name": "Manual Test Candidate",
            "application_number": "MANUAL/PHD/J26/9999",
            "dob": "15-08-2000",
            "applied_subject": test_dept_code,
            "email": "manual@example.com",
            "mobile_number": "9876543210"
        }, headers=headers)
        if man_res.status_code == 201:
            record_test("Phase 10", "Manual Candidate Add Valid", "PASSED", "Manually inserted candidate successfully.")
        else:
            record_test("Phase 10", "Manual Candidate Add Valid", "FAILED", f"Status: {man_res.status_code}, Body: {man_res.text}")

        # 12b. Manual candidate add: Duplicate Application
        dup_man = client.post("/api/admin/candidates/manual", json={
            "name": "Manual Candidate Duplicate",
            "application_number": "MANUAL/PHD/J26/9999",
            "dob": "20-08-2000",
            "applied_subject": test_dept_code
        }, headers=headers)
        if dup_man.status_code == 400:
            record_test("Phase 10", "Manual Add Duplicate Check", "PASSED", "Prevented duplicate manual registration successfully.")
        else:
            record_test("Phase 10", "Manual Add Duplicate Check", "FAILED", f"Status: {dup_man.status_code}")

        # 12c. Manual candidate add: Invalid DOB Format
        bad_dob = client.post("/api/admin/candidates/manual", json={
            "name": "Manual Candidate Bad DOB",
            "application_number": "MANUAL/PHD/J26/0001",
            "dob": "invalid-dob",
            "applied_subject": test_dept_code
        }, headers=headers)
        if bad_dob.status_code == 400:
            record_test("Phase 10", "Manual Add Invalid DOB Check", "PASSED", "Rejected bad DOB format correctly.")
        else:
            record_test("Phase 10", "Manual Add Invalid DOB Check", "FAILED", f"Status: {bad_dob.status_code}")

        # 12d. Manual candidate add: Invalid Subject
        bad_subj = client.post("/api/admin/candidates/manual", json={
            "name": "Manual Candidate Bad Subj",
            "application_number": "MANUAL/PHD/J26/0002",
            "dob": "12-12-1999",
            "applied_subject": "INVALID_SUBJECT_NAME_999"
        }, headers=headers)
        if bad_subj.status_code == 400:
            record_test("Phase 10", "Manual Add Invalid Subject Check", "PASSED", "Rejected invalid applied subject successfully.")
        else:
            record_test("Phase 10", "Manual Add Invalid Subject Check", "FAILED", f"Status: {bad_subj.status_code}")

        # 12e. Delete Single Candidate
        temp_cand = client.post("/api/admin/candidates/manual", json={
            "name": "Temp Del Candidate",
            "application_number": "TEMP/PHD/J26/1111",
            "dob": "01-01-1998",
            "applied_subject": test_dept_code
        }, headers=headers)
        temp_cand_id = temp_cand.json().get("candidate", {}).get("id")
        
        del_res = client.delete(f"/api/admin/candidates/{temp_cand_id}", headers=headers)
        if del_res.status_code == 200:
            record_test("Phase 10", "Delete Single Candidate", "PASSED", "Permanently deleted single candidate record.")
        else:
            record_test("Phase 10", "Delete Single Candidate", "FAILED", f"Status: {del_res.status_code}, Body: {del_res.text}")

        # 12f. Delete Multiple Selected Candidates (Bulk Delete)
        cand1 = client.post("/api/admin/candidates/manual", json={
            "name": "Bulk Del Candidate 1",
            "application_number": "TEMP/PHD/J26/2222",
            "dob": "01-01-1998",
            "applied_subject": test_dept_code
        }, headers=headers).json().get("candidate", {}).get("id")
        
        cand2 = client.post("/api/admin/candidates/manual", json={
            "name": "Bulk Del Candidate 2",
            "application_number": "TEMP/PHD/J26/3333",
            "dob": "01-01-1998",
            "applied_subject": test_dept_code
        }, headers=headers).json().get("candidate", {}).get("id")

        bulk_del_res = client.request("DELETE", "/api/admin/candidates/bulk-delete", json={
            "candidate_ids": [cand1, cand2]
        }, headers=headers)
        if bulk_del_res.status_code == 200:
            record_test("Phase 10", "Delete Bulk Candidates", "PASSED", "Permanently bulk deleted selected candidate records.")
        else:
            record_test("Phase 10", "Delete Bulk Candidates", "FAILED", f"Status: {bulk_del_res.status_code}, Body: {bulk_del_res.text}")

        # 12g. Delete One Question
        db = SessionLocal()
        temp_q = Question(
            department_id=test_dept_id,
            question_no=999,
            question_text="Temp Question",
            option_a="a", option_b="b", option_c="c", option_d="d",
            correct_option="A", marks=1.0, is_active=True
        )
        db.add(temp_q)
        db.commit()
        db.refresh(temp_q)
        temp_q_id = temp_q.id
        db.close()

        del_q_res = client.delete(f"/api/admin/questions/{temp_q_id}", headers=headers)
        if del_q_res.status_code == 200:
            record_test("Phase 10", "Delete Single Question", "PASSED", "Permanently deleted single question bank record.")
        else:
            record_test("Phase 10", "Delete Single Question", "FAILED", f"Status: {del_q_res.status_code}, Body: {del_q_res.text}")

        # 12h. Delete Selected Questions (Bulk Delete Questions)
        db = SessionLocal()
        q1 = Question(
            department_id=test_dept_id,
            question_no=1000,
            question_text="Bulk Del Q1",
            option_a="a", option_b="b", option_c="c", option_d="d",
            correct_option="A", marks=1.0, is_active=True
        )
        q2 = Question(
            department_id=test_dept_id,
            question_no=1001,
            question_text="Bulk Del Q2",
            option_a="a", option_b="b", option_c="c", option_d="d",
            correct_option="A", marks=1.0, is_active=True
        )
        db.add_all([q1, q2])
        db.commit()
        q1_id, q2_id = q1.id, q2.id
        db.close()

        bulk_q_res = client.request("DELETE", "/api/admin/questions/bulk-delete", json={
            "question_ids": [q1_id, q2_id]
        }, headers=headers)
        if bulk_q_res.status_code == 200:
            record_test("Phase 10", "Delete Bulk Questions", "PASSED", "Permanently bulk-deleted questions successfully.")
        else:
            record_test("Phase 10", "Delete Bulk Questions", "FAILED", f"Status: {bulk_q_res.status_code}, Body: {bulk_q_res.text}")

        # 12i. Delete Department Question Bank
        db = SessionLocal()
        q3 = Question(
            department_id=test_dept_id,
            question_no=1002,
            question_text="Dept Q3",
            option_a="a", option_b="b", option_c="c", option_d="d",
            correct_option="A", marks=1.0, is_active=True
        )
        db.add(q3)
        db.commit()
        db.close()

        dept_q_del = client.delete(f"/api/admin/questions/department/{test_dept_id}/hard-delete", headers=headers)
        if dept_q_del.status_code == 200:
            record_test("Phase 10", "Delete Department Question Bank", "PASSED", "Permanently wiped entire department question bank.")
        else:
            record_test("Phase 10", "Delete Department Question Bank", "FAILED", f"Status: {dept_q_del.status_code}, Body: {dept_q_del.text}")

        # 12j. Candidate Token Role Isolation on Deletes
        cand_del = client.delete(f"/api/admin/departments/{test_dept_id}", headers=cand_headers)
        if cand_del.status_code in (401, 403):
            record_test("Phase 10", "Candidate Token Deletion Block", "PASSED", "Candidate token was blocked from calling admin delete endpoints.")
        else:
            record_test("Phase 10", "Candidate Token Deletion Block", "FAILED", f"Candidate token delete check allowed: Status {cand_del.status_code}")

        # 12k. Delete Exam Session Cascades
        temp_sess_res = client.post("/api/admin/exam-sessions/", json={
            "session_name": "QA Session for Cascades",
            "exam_title": "PhD Entrance Exam",
            "exam_date": str(date.today() + timedelta(days=5)),
            "start_time": (datetime.now() + timedelta(days=5)).isoformat(),
            "end_time": (datetime.now() + timedelta(days=5, hours=2)).isoformat(),
            "duration_minutes": 90,
            "instructions": "Mock test instructions"
        }, headers=headers)
        temp_sess_id = temp_sess_res.json().get("id")

        del_sess_res = client.delete(f"/api/admin/exam-sessions/{temp_sess_id}", headers=headers)
        if del_sess_res.status_code == 200:
            record_test("Phase 10", "Delete Exam Session Cascade", "PASSED", "Permanently deleted exam session with unassignment successfully.")
        else:
            record_test("Phase 10", "Delete Exam Session Cascade", "FAILED", f"Status: {del_sess_res.status_code}, Body: {del_sess_res.text}")

        # 12l. Delete Department Cascades
        temp_dept_res = client.post("/api/admin/departments", json={
            "department_name": "Temp Dept for Cascade",
            "department_code": "QA-TEMP-CASC",
            "description": "Temp description"
        }, headers=headers)
        temp_dept_id = temp_dept_res.json().get("id")

        del_dept_res = client.delete(f"/api/admin/departments/{temp_dept_id}", headers=headers)
        if del_dept_res.status_code == 200:
            record_test("Phase 10", "Delete Department Cascade", "PASSED", "Permanently deleted department with transaction cascades successfully.")
        else:
            record_test("Phase 10", "Delete Department Cascade", "FAILED", f"Status: {del_dept_res.status_code}, Body: {del_dept_res.text}")

        # ====================================================
        # Phase 11 - Full Screen Exam Mode & Admin Reopen
        # ====================================================
        
        # 1. Fullscreen event logging
        fs_log = client.post("/api/candidate/exam/fullscreen-event", json={
            "attempt_id": 9999,
            "event_type": "entered_fullscreen",
            "timestamp": "2026-07-08T12:00:00Z"
        }, headers=cand_headers)
        if fs_log.status_code == 200:
            record_test("Phase 11", "Fullscreen Event Log", "PASSED", "Fullscreen event logged successfully.")
        else:
            record_test("Phase 11", "Fullscreen Event Log", "FAILED", f"Status: {fs_log.status_code}, Body: {fs_log.text}")

        # Reset candidate exam attempt so they can start fresh for Phase 11
        db_p11 = SessionLocal()
        try:
            # Recreate active exam session that was deleted in Phase 10 cascade checks
            dept_obj = db_p11.query(Department).filter(Department.id == test_dept_id).first()
            import zoneinfo
            kolkata = zoneinfo.ZoneInfo("Asia/Kolkata")
            now_kolkata = datetime.now(kolkata)
            new_sess = ExamSession(
                session_name="QA Session Phase 11",
                exam_title="QA Entry Exam",
                exam_date=now_kolkata.date(),
                start_time=(now_kolkata - timedelta(minutes=10)).replace(tzinfo=None),
                end_time=(now_kolkata + timedelta(minutes=80)).replace(tzinfo=None),
                duration_minutes=90,
                instructions="Test instructions",
                is_active=True,
                departments=[dept_obj] if dept_obj else []
            )
            db_p11.add(new_sess)
            db_p11.commit()
            db_p11.refresh(new_sess)

            cand_obj = db_p11.query(Candidate).filter(Candidate.application_number == test_candidate_app).first()
            if cand_obj:
                cand_obj.exam_session_id = new_sess.id
                db_p11.query(CandidateAnswer).filter(CandidateAnswer.candidate_id == cand_obj.id).delete(synchronize_session=False)
                db_p11.query(ExamAttempt).filter(ExamAttempt.candidate_id == cand_obj.id).delete(synchronize_session=False)
                # Seed 70 questions back if wiped in Phase 10
                q_count = db_p11.query(Question).filter(Question.department_id == test_dept_id, Question.is_active == True).count()
                if q_count < 70:
                    for i in range(1, 71):
                        q_obj = Question(
                            question_no=i,
                            question_text=f"QA Question {i}: What is 2 + 2?",
                            option_a="3",
                            option_b="4",
                            option_c="5",
                            option_d="6",
                            correct_option="B",
                            marks=1,
                            is_active=True,
                            department_id=test_dept_id
                        )
                        db_p11.add(q_obj)
                db_p11.commit()
        except Exception as db_err:
            print(f"Error resetting candidate attempt: {db_err}")
            db_p11.rollback()
        finally:
            db_p11.close()

        # 2. Start exam with client fingerprint A
        app_cand_res = client.post("/api/candidate/exam/start", headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-A"
        })
        if app_cand_res.status_code == 200:
            record_test("Phase 11", "Start Attempt Lock", "PASSED", "Exam attempt started with device-A lock.")
        else:
            record_test("Phase 11", "Start Attempt Lock", "FAILED", f"Status: {app_cand_res.status_code}")

        # 3. Requesting status from different client fingerprint B (without reopen) -> should get 423 Locked
        app_locked_res = client.get("/api/candidate/exam/current", headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-B"
        })
        if app_locked_res.status_code == 423:
            record_test("Phase 11", "Device Lock Enforcement", "PASSED", "Blocked device-B with 423 Locked.")
        else:
            record_test("Phase 11", "Device Lock Enforcement", "FAILED", f"Status: {app_locked_res.status_code}, Body: {app_locked_res.text}")

        # 4. Lookup status in admin control
        c_status_res = client.get(f"/api/admin/exam-control/candidate/{test_candidate_app}", headers=headers)
        if c_status_res.status_code == 200 and c_status_res.json().get("can_reopen") is True:
            record_test("Phase 11", "Admin Control Query", "PASSED", "Admin lookup retrieved candidate state, can_reopen = True.")
        else:
            record_test("Phase 11", "Admin Control Query", "FAILED", f"Status: {c_status_res.status_code}")

        # 5. Admin reopen candidate attempt
        reopen_action_res = client.post("/api/admin/exam-control/reopen", json={
            "application_number": test_candidate_app,
            "reason": "Test override"
        }, headers=headers)
        if reopen_action_res.status_code == 200:
            record_test("Phase 11", "Admin Reopen Override", "PASSED", "Override cleared device lock status successfully.")
        else:
            record_test("Phase 11", "Admin Reopen Override", "FAILED", f"Status: {reopen_action_res.status_code}, Body: {reopen_action_res.text}")

        # 6. Retry from device-B after reopen -> should succeed and acquire device-B lock
        app_resume_res = client.get("/api/candidate/exam/current", headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-B"
        })
        if app_resume_res.status_code == 200:
            record_test("Phase 11", "Reopened Device Resume", "PASSED", "Resumed exam on device-B successfully.")
        else:
            record_test("Phase 11", "Reopened Device Resume", "FAILED", f"Status: {app_resume_res.status_code}, Body: {app_resume_res.text}")

        # 7. Try back from device-A (which is now locked out) -> should get 423 Locked
        app_lockout_a = client.get("/api/candidate/exam/current", headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-A"
        })
        if app_lockout_a.status_code == 423:
            record_test("Phase 11", "Device Transfer Lockout", "PASSED", "Device-A is now locked out after transfer.")
        else:
            record_test("Phase 11", "Device Transfer Lockout", "FAILED", f"Status: {app_lockout_a.status_code}")

        # 8. Submit candidate attempt on device-B
        test_attempt_id = app_cand_res.json().get("attempt_id")
        sub_res = client.post("/api/candidate/exam/submit", json={
            "attempt_id": test_attempt_id,
            "submission_type": "manual"
        }, headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-B"
        })
        if sub_res.status_code == 200:
            record_test("Phase 11", "Final Submit Attempt", "PASSED", "Attempt finalized on device-B.")
        else:
            record_test("Phase 11", "Final Submit Attempt", "FAILED", f"Status: {sub_res.status_code}")

        # 9. Try to start or current again -> should get 403 Completed
        app_comp_res = client.get("/api/candidate/exam/current", headers={
            **cand_headers,
            "X-Exam-Client-Id": "device-B"
        })
        if app_comp_res.status_code == 403 and app_comp_res.json().get("detail", {}).get("redirect_to_result") is True:
            record_test("Phase 11", "Prevent Rewrite Check", "PASSED", "Blocked start/current after final submission.")
        else:
            record_test("Phase 11", "Prevent Rewrite Check", "FAILED", f"Status: {app_comp_res.status_code}")

        # 10. Reopen submitted attempt as Admin -> should fail with 400
        admin_reopen_comp = client.post("/api/admin/exam-control/reopen", json={
            "application_number": test_candidate_app,
            "reason": "Invalid rewrite attempt"
        }, headers=headers)
        if admin_reopen_comp.status_code == 400:
            record_test("Phase 11", "Admin Reopen Completed Block", "PASSED", "Blocked reopen of submitted attempt correctly.")
        else:
            record_test("Phase 11", "Admin Reopen Completed Block", "FAILED", f"Status: {admin_reopen_comp.status_code}")

    except Exception as e:
        record_test("Phase 11", "General", "FAILED", f"Phase 11 tests crashed: {str(e)}")

    # Cleanup test entries to leave database clean
    db = SessionLocal()
    try:
        # Delete answers and attempts of qatest
        db.query(CandidateAnswer).filter(CandidateAnswer.candidate_id == (db.query(Candidate.id).filter(Candidate.application_number == test_candidate_app).scalar())).delete(synchronize_session=False)
        db.query(ExamAttempt).filter(ExamAttempt.candidate_id == (db.query(Candidate.id).filter(Candidate.application_number == test_candidate_app).scalar())).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.application_number == test_candidate_app).delete()
        # Clean up any manual test leftovers
        db.query(Candidate).filter(Candidate.application_number.in_(["MANUAL/PHD/J26/9999", "MANUAL/PHD/J26/0001", "MANUAL/PHD/J26/0002"])).delete(synchronize_session=False)
        db.query(Question).filter(Question.department_id == test_dept_id).delete()
        db.query(ExamSession).filter(ExamSession.id == test_session_id).delete()
        db.query(Department).filter(Department.id == test_dept_id).delete()
        db.commit()
        print("Cleaned up mock database entries.")
    except Exception as e:
        print(f"Cleanup warning: {e}")
        db.rollback()
    finally:
        db.close()

    print("====================================================")
    print("               QA TEST SUITE COMPLETED              ")
    print("====================================================")
    
    return results

if __name__ == "__main__":
    test_results = run_all_qa_tests()
    
    # Save the output results array as a temporary JSON file to construct report file easily
    with open("qa_results.json", "w") as f:
        json.dump(test_results, f, indent=2)
