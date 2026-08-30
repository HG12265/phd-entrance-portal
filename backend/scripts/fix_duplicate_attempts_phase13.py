import os
import sys
import json

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models.exam_attempt import ExamAttempt

def fix_duplicate_attempts():
    db = SessionLocal()
    
    # Summary counters
    groups_checked = 0
    official_attempts_kept = 0
    duplicates_invalidated = 0

    try:
        # Find all distinct groups of candidate_id + exam_session_id that have attempts
        groups = db.query(ExamAttempt.candidate_id, ExamAttempt.exam_session_id).distinct().all()
        
        for candidate_id, exam_session_id in groups:
            groups_checked += 1
            
            # Fetch all completed attempts in the group sorted by:
            # submitted_time IS NULL ASC, submitted_time ASC, id ASC
            completed_attempts = db.query(ExamAttempt).filter(
                ExamAttempt.candidate_id == candidate_id,
                ExamAttempt.exam_session_id == exam_session_id,
                ExamAttempt.status.in_(["submitted", "auto_submitted"])
            ).order_by(
                ExamAttempt.submitted_time.is_(None).asc(),
                ExamAttempt.submitted_time.asc(),
                ExamAttempt.id.asc()
            ).all()

            if not completed_attempts:
                continue

            # Keep the first completed attempt as official
            official_attempt = completed_attempts[0]
            official_attempts_kept += 1

            # Mark subsequent completed attempts as invalidated_duplicate
            for dup in completed_attempts[1:]:
                if dup.status != "invalidated_duplicate":
                    dup.status = "invalidated_duplicate"
                    duplicates_invalidated += 1

            # Also, find any other attempts in the group (like in_progress or expired)
            # which are NOT part of the completed list and are later than the official attempt.
            # (We mark any other in_progress or expired attempt for this candidate+session as invalidated_duplicate
            # because the candidate already has an official completed attempt).
            completed_ids = {c.id for c in completed_attempts}
            other_attempts = db.query(ExamAttempt).filter(
                ExamAttempt.candidate_id == candidate_id,
                ExamAttempt.exam_session_id == exam_session_id,
                ~ExamAttempt.id.in_(completed_ids),
                ExamAttempt.status.in_(["in_progress", "expired"])
            ).all()

            for other in other_attempts:
                if other.status != "invalidated_duplicate":
                    other.status = "invalidated_duplicate"
                    duplicates_invalidated += 1

        db.commit()
        
        summary = {
            "groups_checked": groups_checked,
            "official_attempts_kept": official_attempts_kept,
            "duplicates_invalidated": duplicates_invalidated
        }
        print(json.dumps(summary, indent=2))

    except Exception as e:
        db.rollback()
        print(f"Error executing cleanup script: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_duplicate_attempts()
