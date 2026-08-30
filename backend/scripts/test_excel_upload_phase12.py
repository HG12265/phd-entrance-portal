import os
import sys
import requests
from sqlalchemy.orm import Session

# Ensure backend/ is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.candidate import Candidate
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer

def run_upload_test():
    print("==================================================")
    print("Testing Candidate Upload with Official Excel Report")
    print("==================================================")

    # 1. Clear database candidates so we do not have duplicates blocking the upload
    db = SessionLocal()
    try:
        # Delete answers and attempts first to satisfy foreign keys
        db.query(CandidateAnswer).delete()
        db.query(ExamAttempt).delete()
        db.query(Candidate).delete()
        db.commit()
        print("[PASS] Cleaned up existing database candidate entries.")
    finally:
        db.close()

    # 2. Authenticate as Admin
    login_url = "http://127.0.0.1:8000/api/admin/auth/login"
    login_payload = {
        "email": "admin@phdportal.com",
        "password": "Admin@123"
    }
    
    try:
        r = requests.post(login_url, json=login_payload)
        r.raise_for_status()
        token = r.json()["access_token"]
        print("[PASS] Admin authentication successful.")
    except Exception as e:
        print(f"[FAIL] Admin authentication failed: {str(e)}")
        sys.exit(1)

    # 3. Post Excel file
    excel_path = "c:\\Users\\Gowtham\\Downloads\\applications_1783491694697.xlsx"
    if not os.path.exists(excel_path):
        print(f"[FAIL] Target Excel file not found at: {excel_path}")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    upload_url = "http://127.0.0.1:8000/api/admin/candidates/upload-excel"
    print(f"Uploading file: {excel_path} to {upload_url}...")
    
    try:
        with open(excel_path, "rb") as f:
            files = {"file": (os.path.basename(excel_path), f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            r = requests.post(upload_url, headers=headers, files=files)
            r.raise_for_status()
            res_data = r.json()
            
            print("\n--- Upload Result Summary ---")
            print(f"Message: {res_data.get('message')}")
            print(f"Total Rows: {res_data.get('total_rows')}")
            print(f"Success Count: {res_data.get('success_count')}")
            print(f"Failed Count: {res_data.get('failed_count')}")
            print(f"Photo Available: {res_data.get('photo_available_count')}")
            print(f"Photo Missing: {res_data.get('photo_missing_count')}")
            print(f"Duplicate in Excel: {res_data.get('duplicate_in_excel_count')}")
            print(f"Duplicate in DB: {res_data.get('duplicate_in_database_count')}")
            
            # Print first few errors if any
            errors = res_data.get("errors", [])
            if errors:
                print(f"\nErrors list (first 10 of {len(errors)}):")
                for err in errors[:10]:
                    print(f"  Row {err['row']} (App ID: {err.get('application_id')}): {err['error']}")
            
            assert res_data.get("success_count", 0) > 0, "No candidates were successfully uploaded"
            print("\n[PASS] Excel candidate import test succeeded!")
    except Exception as e:
        print(f"[FAIL] Upload request failed: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    run_upload_test()
