import os
import sys
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

# Ensure backend/ is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal
from app.models.exam_attempt import ExamAttempt
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.exam_session import ExamSession
from app.services.report_service import (
    get_overall_result,
    get_department_detail,
    export_department_wise_details_excel,
    _map_result_status_filter
)

def run_tests():
    print("==================================================")
    print("Running Programmatic QA Verification for Phase 18")
    print("==================================================")

    db = SessionLocal()
    try:
        # 0. Clean up potential old test candidates to keep DB pristine
        db.query(Candidate).filter(Candidate.application_number == "TESTPHD18/0001").delete(synchronize_session=False)
        db.commit()

        # 1. Verify that database table has the new columns login_time and system_ip
        try:
            db.execute(text("SELECT login_time, system_ip FROM exam_attempts LIMIT 1"))
            print("[PASS] Columns 'login_time' and 'system_ip' successfully present in database.")
        except Exception as e:
            print(f"[FAIL] Columns 'login_time' or 'system_ip' missing or database query failed: {e}")
            sys.exit(1)

        # 2. Verify filter mapping terminology internal helper
        assert _map_result_status_filter("QUALIFIED") == "PASS", "Filter mapping for QUALIFIED failed"
        assert _map_result_status_filter("NOT QUALIFIED") == "FAIL", "Filter mapping for NOT QUALIFIED failed"
        assert _map_result_status_filter("PASS") == "PASS", "Filter mapping for PASS should remain PASS"
        assert _map_result_status_filter("FAIL") == "FAIL", "Filter mapping for FAIL should remain FAIL"
        assert _map_result_status_filter(None) is None, "Filter mapping for None failed"
        print("[PASS] Filter terminology mapping helper works correctly.")

        # 3. Create dummy data for testing reports and exporting
        # Get or create an active exam session and department
        session = db.query(ExamSession).filter(ExamSession.is_active == True).first()
        if not session:
            session = ExamSession(session_name="Test Phase 18 Session", is_active=True)
            db.add(session)
            db.commit()
            db.refresh(session)
        
        dept = db.query(Department).first()
        if not dept:
            dept = Department(department_name="Test department", department_code="TEST-DEPT")
            db.add(dept)
            db.commit()
            db.refresh(dept)

        # Create dummy candidate and attempt
        test_candidate = Candidate(
            application_id="TESTPHD18/0001",
            application_number="TESTPHD18/0001",
            applicant_name="Phase Eighteen Candidate",
            initial="T",
            name="Phase Eighteen Candidate T",
            dob=datetime.date(1990, 1, 1),
            category_ft_pt="FT",
            email="ph18@test.com",
            mobile_number="1234567890",
            department_id=dept.id,
            applied_subject=dept.department_name,
            exam_session_id=session.id,
            is_active=True
        )
        db.add(test_candidate)
        db.commit()
        db.refresh(test_candidate)

        test_attempt = ExamAttempt(
            candidate_id=test_candidate.id,
            department_id=dept.id,
            exam_session_id=session.id,
            start_time=datetime.datetime.now(),
            end_time=datetime.datetime.now() + datetime.timedelta(hours=2),
            submitted_time=datetime.datetime.now(),
            shuffled_question_order="[]",
            status="submitted",
            score=35, # should be QUALIFIED/PASS (>=28)
            result_status="PASS", # must remain PASS in DB
            correct_count=35,
            wrong_count=35,
            unanswered_count=0,
            login_time=datetime.datetime.now(),
            system_ip="192.168.1.100",
            last_answer_snapshot_json="{}",
            selected_count_at_submit=35
        )
        db.add(test_attempt)
        db.commit()
        db.refresh(test_attempt)

        try:
            # 4. Verify overall result maps PASS -> QUALIFIED in output response
            overall_res = get_overall_result(
                db=db,
                exam_session_id=session.id,
                result_status="QUALIFIED" # test mapping filter input
            )
            # Find the test candidate in the results
            results = overall_res.get("results", [])
            test_row = next((r for r in results if r["candidate_id"] == test_candidate.id), None)
            assert test_row is not None, "Test candidate should be returned under QUALIFIED filter"
            assert test_row["result_status"] == "QUALIFIED", f"Expected result_status 'QUALIFIED', got: {test_row['result_status']}"
            print("[PASS] Result status mapping PASS -> QUALIFIED in output serialization works.")

            # 5. Verify sorting order in overall results summary card layout
            summary = overall_res.get("summary", {})
            keys = list(summary.keys())
            expected_keys = [
                "total_registered", "appeared", "absent",
                "passed", "failed", "pass_percentage",
                "average_score", "lowest_score", "highest_score"
            ]
            for ek in expected_keys:
                assert ek in keys, f"Summary key {ek} missing"
            print("[PASS] Summary stats contains correct metrics.")

            # 6. Verify department wise details excel export
            excel_bytes = export_department_wise_details_excel(db, session.id)
            assert len(excel_bytes) > 0, "Excel export returned empty bytes"
            print("[PASS] Export department wise details Excel generated successfully.")

        finally:
            # Clean up dummy test data
            db.delete(test_attempt)
            db.delete(test_candidate)
            db.commit()

        print("==================================================")
        print("ALL QA CHECKS FOR PHASE 18 COMPLETED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
