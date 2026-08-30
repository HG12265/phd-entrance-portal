#!/usr/bin/env python3
"""
Phase 17 Test: First Force Reopen Preserves Answers.
Run from backend/: python scripts/test_phase17_first_reopen_preserves_answers.py
"""
import os, sys, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer

BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "adminpassword"

PASS = "[PASS]"
FAIL = "[FAIL]"

def print_result(label, ok, detail=""):
    status = PASS if ok else FAIL
    print(f"  {status} {label}" + (f" -- {detail}" if detail else ""))
    return ok

def run_tests():
    db = SessionLocal()
    all_ok = True
    try:
        # 1. Find test candidate with department_id assigned
        candidate = db.query(Candidate).filter(
            Candidate.department_id.isnot(None)
        ).first()
        if not candidate:
            print("[ERROR] No candidate with department_id found. Cannot run test.")
            return False

        application_id = candidate.application_id or candidate.application_number
        print(f"\nUsing candidate: {candidate.name} | app_id={application_id}")

        # 2. Get admin token
        r = requests.post(f"{BASE_URL}/api/admin/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        if r.status_code != 200:
            print(f"[ERROR] Admin login failed: {r.text}")
            return False
        admin_token = r.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("Admin logged in OK")

        # 3. Check existing state
        existing_attempts = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == candidate.id
        ).all()
        print(f"Existing attempts for candidate: {len(existing_attempts)}")
        for a in existing_attempts:
            print(f"  attempt_id={a.id} status={a.status} submitted_reopen_count={a.submitted_reopen_count}")

        # Find submitted attempt
        submitted = db.query(ExamAttempt).filter(
            ExamAttempt.candidate_id == candidate.id,
            ExamAttempt.status.in_(["submitted", "auto_submitted"])
        ).first()

        if not submitted:
            print("\n[INFO] No submitted attempt found. Manual test needed (start exam + submit first).")
            print("[INFO] This script verifies DB-level answer preservation on force reopen.")
            print("[INFO] Run after: candidate logs in, answers 10 questions, submits.")
            return True

        attempt = submitted
        attempt_id = attempt.id

        # 4. Count selected answers BEFORE force reopen
        selected_before = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == attempt_id,
            CandidateAnswer.selected_option.isnot(None),
            CandidateAnswer.selected_option != ""
        ).count()
        answer_rows = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == attempt_id
        ).count()

        print(f"\nBEFORE Force Reopen:")
        print(f"  attempt_id={attempt_id} status={attempt.status}")
        print(f"  selected_count={selected_before} total_rows={answer_rows}")
        ok = print_result("Selected answers exist before reopen", selected_before > 0,
                          f"selected={selected_before}")
        all_ok = all_ok and ok

        # 5. Admin force reopen
        print(f"\nCalling force-reopen-submitted for {application_id}...")
        r = requests.post(
            f"{BASE_URL}/api/admin/exam-control/force-reopen-submitted",
            json={
                "application_number": application_id,
                "reason": "Phase 17 test reopen",
                "confirm_text": "REOPEN",
                "extra_minutes": 30
            },
            headers=admin_headers
        )
        if r.status_code != 200:
            print(f"[ERROR] Force reopen failed: {r.status_code} {r.text}")
            return False

        reopen_resp = r.json()
        print(f"Force reopen response: {json.dumps(reopen_resp, indent=2)}")

        ok = print_result("Force reopen returned 200", True)
        all_ok = all_ok and ok
        ok = print_result("same attempt_id returned", reopen_resp.get("attempt_id") == attempt_id,
                          f"expected={attempt_id} got={reopen_resp.get('attempt_id')}")
        all_ok = all_ok and ok
        ok = print_result("selected_answers_preserved >= selected_before",
                          reopen_resp.get("selected_count_after", 0) >= selected_before,
                          f"before={selected_before} after={reopen_resp.get('selected_count_after')}")
        all_ok = all_ok and ok

        # 6. Verify DB after reopen
        db.expire_all()
        attempt_after = db.query(ExamAttempt).filter(ExamAttempt.id == attempt_id).first()
        selected_after = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == attempt_id,
            CandidateAnswer.selected_option.isnot(None),
            CandidateAnswer.selected_option != ""
        ).count()
        answer_rows_after = db.query(CandidateAnswer).filter(
            CandidateAnswer.attempt_id == attempt_id
        ).count()

        print(f"\nAFTER Force Reopen (DB verify):")
        print(f"  status={attempt_after.status} lock_status={attempt_after.lock_status}")
        print(f"  selected_count={selected_after} total_rows={answer_rows_after}")
        print(f"  reopened_from_submitted={attempt_after.reopened_from_submitted}")
        print(f"  submitted_reopen_count={attempt_after.submitted_reopen_count}")

        ok = print_result("Attempt status is in_progress", attempt_after.status == "in_progress",
                          f"got={attempt_after.status}")
        all_ok = all_ok and ok
        ok = print_result("Lock status is reopened", attempt_after.lock_status == "reopened",
                          f"got={attempt_after.lock_status}")
        all_ok = all_ok and ok
        ok = print_result("selected_count preserved after reopen",
                          selected_after == selected_before,
                          f"before={selected_before} after={selected_after}")
        all_ok = all_ok and ok
        ok = print_result("answer_rows count unchanged",
                          answer_rows_after == answer_rows,
                          f"before={answer_rows} after={answer_rows_after}")
        all_ok = all_ok and ok
        ok = print_result("reopened_from_submitted=True",
                          attempt_after.reopened_from_submitted == True)
        all_ok = all_ok and ok
        ok = print_result("No new attempt created",
                          db.query(ExamAttempt).filter(
                              ExamAttempt.candidate_id == candidate.id
                          ).count() == len(existing_attempts),
                          f"before={len(existing_attempts)} after={db.query(ExamAttempt).filter(ExamAttempt.candidate_id==candidate.id).count()}")
        all_ok = all_ok and ok

        # 7. Verify snapshot saved on last submit
        print(f"\nSnapshot check:")
        ok = print_result("last_answer_snapshot_json is set",
                          attempt_after.last_answer_snapshot_json is not None,
                          "Snapshot present in DB")
        all_ok = all_ok and ok
        if attempt_after.last_answer_snapshot_json:
            snap = json.loads(attempt_after.last_answer_snapshot_json)
            snap_selected = sum(1 for s in snap if s.get("selected_option"))
            ok = print_result("Snapshot selected_count matches DB",
                              snap_selected == selected_before,
                              f"snapshot={snap_selected} db_before={selected_before}")
            all_ok = all_ok and ok

        print()
        if all_ok:
            print("=" * 50)
            print(f"  ALL TESTS PASSED — Phase 17 answer preservation OK")
            print("=" * 50)
        else:
            print("=" * 50)
            print(f"  SOME TESTS FAILED — Review output above")
            print("=" * 50)

        return all_ok

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Test exception: {e}")
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)