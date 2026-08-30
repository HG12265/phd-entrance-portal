import os
import sys
import shutil

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.candidate_answer import CandidateAnswer
from app.models.exam_attempt import ExamAttempt
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.exam_session import ExamSession

def clear_all_except_admin_and_depts():
    db = SessionLocal()
    try:
        print("Starting data purge...")

        # 1. Delete CandidateAnswer
        ans_count = db.query(CandidateAnswer).delete(synchronize_session=False)
        print(f"Deleted {ans_count} CandidateAnswer rows.")

        # 2. Delete ExamAttempt
        attempt_count = db.query(ExamAttempt).delete(synchronize_session=False)
        print(f"Deleted {attempt_count} ExamAttempt rows.")

        # 3. Delete Candidate
        cand_count = db.query(Candidate).delete(synchronize_session=False)
        print(f"Deleted {cand_count} Candidate rows.")

        # 4. Delete Question
        q_count = db.query(Question).delete(synchronize_session=False)
        print(f"Deleted {q_count} Question rows.")

        # 5. Delete ExamSession
        session_count = db.query(ExamSession).delete(synchronize_session=False)
        print(f"Deleted {session_count} ExamSession rows.")

        db.commit()
        print("Database cleanup completed successfully.")

        # Clean upload directories
        upload_dirs = [
            os.path.join("uploads", "candidate_photos"),
            os.path.join("uploads", "candidate_excels"),
            os.path.join("uploads", "question_excels")
        ]

        for folder in upload_dirs:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"Failed to delete {file_path}. Reason: {e}")
                print(f"Cleared upload directory: {folder}")

        print("Purge task complete.")

    except Exception as e:
        db.rollback()
        print(f"Data purge failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_except_admin_and_depts()
