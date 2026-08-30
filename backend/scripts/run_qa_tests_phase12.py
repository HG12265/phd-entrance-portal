import os
import sys
import datetime
from sqlalchemy.orm import Session

# Ensure backend/ is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, SessionLocal
from app.models.candidate import Candidate
from app.models.department import Department
from app.models.exam_session import ExamSession
from app.utils.excel_utils import (
    resolve_candidate_department,
    find_candidate_photo,
    parse_dob
)

def run_tests():
    print("==================================================")
    print("Running Programmatic QA Verification for Phase 12")
    print("==================================================")

    db = SessionLocal()
    try:
        # 1. Clean up potential old test candidates to keep DB pristine
        db.query(Candidate).filter(Candidate.application_id.like("TESTCET%")).delete(synchronize_session=False)
        db.commit()

        # 2. Assert Departments exist
        depts = db.query(Department).all()
        if not depts:
            print("[FAIL] No departments found in database. Seed departments first.")
            sys.exit(1)
        print(f"[PASS] Active departments found: {len(depts)}")

        # 3. Verify resolve_candidate_department mapping priority rules
        # Find Computer Science dept code or name
        cs_dept = next((d for d in depts if "computer" in d.department_name.lower() or "cs" in d.department_code.lower()), None)
        if cs_dept:
            # Test exact name match
            res = resolve_candidate_department(cs_dept.department_name, "Physics", depts)
            assert res["id"] == cs_dept.id, f"Exact name match failed for {cs_dept.department_name}"
            
            # Test exact code match
            res = resolve_candidate_department(cs_dept.department_code, "Physics", depts)
            assert res["id"] == cs_dept.id, f"Exact code match failed for {cs_dept.department_code}"

            # Test case-insensitive trimmed match
            res = resolve_candidate_department(f"  {cs_dept.department_name.upper()}  ", "Physics", depts)
            assert res["id"] == cs_dept.id, "Case-insensitive trimmed match failed"

            # Test Subject column exact name fallback
            res = resolve_candidate_department(None, cs_dept.department_name, depts)
            assert res["id"] == cs_dept.id, "Subject exact fallback failed"

            # Test Subject column code fallback
            res = resolve_candidate_department("", cs_dept.department_code, depts)
            assert res["id"] == cs_dept.id, "Subject code fallback failed"

            # Test contains unique substring match
            # Get part of CS dept name (e.g. "computer" or "science")
            sub_part = "computer" if "computer" in cs_dept.department_name.lower() else cs_dept.department_name[:6]
            res = resolve_candidate_department(sub_part, "", depts)
            assert res["id"] is not None, "Contains substring match failed"

            print("[PASS] Department resolution priority checks succeeded.")
        else:
            print("[WARN] Mapped CS department not found for testing priorities.")

        # 4. Verify parse_dob format resolution
        d1 = parse_dob("15-08-1995")
        assert d1 == datetime.date(1995, 8, 15), f"Failed parsing DD-MM-YYYY: {d1}"
        d2 = parse_dob("1995/08/15")
        assert d2 == datetime.date(1995, 8, 15), f"Failed parsing YYYY/MM/DD: {d2}"
        d3 = parse_dob("15/08/1995")
        assert d3 == datetime.date(1995, 8, 15), f"Failed parsing DD/MM/YYYY: {d3}"
        # Float Excel date serial (42231.0 -> 2015-08-15)
        d4 = parse_dob(42231.0)
        assert d4 == datetime.date(2015, 8, 15), f"Failed parsing Excel date serial: {d4}"
        print("[PASS] Date of Birth parse format checks succeeded.")

        # 5. Verify Photo Mapping resolution logic for CETPHD/J26/0128
        # Create dummy directory if not exists
        os.makedirs(os.path.join("uploads", "candidate_photos"), exist_ok=True)
        dummy_photo = os.path.join("uploads", "candidate_photos", "TESTCETPHD-J26-9999.JPG")
        with open(dummy_photo, "wb") as f:
            f.write(b"dummy")

        try:
            # Check standard name match CETPHD/J26/9999 -> TESTCETPHD-J26-9999
            photo_info = find_candidate_photo("TESTCETPHD/J26/9999")
            print(f"DEBUG Standard photo_info: {photo_info}")
            assert photo_info["photo_status"] == "available", "Photo lookup standard failed"
            assert photo_info["photo_filename"].upper() == "TESTCETPHD-J26-9999.JPG", "Photo filename standard mapping failed"
            
            # Check CET-PHD prefix check for TESTCET/PHD/J26/9999 (should match TESTCETPHD-J26-9999.JPG because starts with TESTCET-PHD- -> TESTCETPHD-)
            # Let's test with starts with CET-PHD
            dummy_photo_alt = os.path.join("uploads", "candidate_photos", "CET-PHD-J26-9999.png")
            with open(dummy_photo_alt, "wb") as f:
                f.write(b"dummy")

            try:
                photo_info_alt = find_candidate_photo("CETPHD/J26/9999")
                assert photo_info_alt["photo_status"] == "available", "Photo lookup alternate failed"
                assert photo_info_alt["photo_filename"].upper() == "CET-PHD-J26-9999.PNG", "Photo filename alternate mapping failed"
            finally:
                if os.path.exists(dummy_photo_alt):
                    os.remove(dummy_photo_alt)

            print("[PASS] Photo filename resolver priority matches succeeded.")
        finally:
            if os.path.exists(dummy_photo):
                os.remove(dummy_photo)

        # 6. Verify manual candidate addition endpoint
        # Simulate payload to manual create candidates using process_candidate_payload helper
        from app.routes.candidate_routes import process_candidate_payload
        dept = depts[0]
        sessions = db.query(ExamSession).filter(ExamSession.is_active == True).all()

        payload = {
            "application_id": "TESTCETPHD/J26/8888",
            "applicant_name": "QA Tester",
            "initial": "B",
            "dob": "10-10-1996",
            "category_ft_pt": "FT",
            "mobile_number": "9876543210",
            "email": "qa@test.com",
            "department": dept.department_name,
            "programme_offered": "Ph.D. Test Programme",
            "subject": dept.department_name
        }

        tracker = set()
        res = process_candidate_payload(
            db=db,
            payload_dict=payload,
            depts=depts,
            active_sessions=sessions,
            excel_duplicates_tracker=tracker
        )
        
        assert res["error"] is None, f"Payload processing failed: {res['error']}"
        cand = res["candidate"]
        assert cand.application_id == "TESTCETPHD/J26/8888", "Payload application_id mapping failed"
        assert cand.application_number == "TESTCETPHD/J26/8888", "Payload application_number mapping failed"
        assert cand.applicant_name == "QA Tester", "Payload applicant_name mapping failed"
        assert cand.name == "QA Tester B", "Payload name combination mapping failed"
        assert cand.initial == "B", "Payload initial mapping failed"
        assert cand.category_ft_pt == "FT", "Payload category_ft_pt mapping failed"
        assert cand.programme_offered == "Ph.D. Test Programme", "Payload programme_offered mapping failed"
        assert cand.department_id == dept.id, "Payload department_id mapping failed"

        # Insert test candidate into DB to check duplicate and login functions
        db.add(cand)
        db.commit()
        db.refresh(cand)

        # Test duplicate application checker
        res_dup = process_candidate_payload(
            db=db,
            payload_dict=payload,
            depts=depts,
            active_sessions=sessions,
            excel_duplicates_tracker=tracker
        )
        assert res_dup["error"] == "Duplicate Application ID.", f"Expected duplicate error but got: {res_dup['error']}"

        # Test candidate login endpoint query using candidate_auth_routes filter matching
        # Lookup candidate using application_id vs application_number
        c_by_num = db.query(Candidate).filter(
            (Candidate.application_number == "TESTCETPHD/J26/8888") |
            (Candidate.application_id == "TESTCETPHD/J26/8888")
        ).first()
        assert c_by_num is not None, "Login lookup failed"
        assert c_by_num.id == cand.id, "Login query did not match correct candidate"

        print("[PASS] Manual creation, duplicate tracking, and login query validations succeeded.")

        # Clean up inserted test candidate
        db.delete(cand)
        db.commit()

        print("==================================================")
        print("ALL QA CHECKS FOR PHASE 12 COMPLETED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
