#!/usr/bin/env python3
"""
Cleanup duplicate exam attempts for candidate sessions.
Keeps the "best" attempt (most answered questions) and marks others as "invalidated_duplicate".
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer

def cleanup():
    db = SessionLocal()
    try:
        # Find candidates with multiple attempts in the same session
        from sqlalchemy import func
        duplicates = db.query(
            ExamAttempt.candidate_id,
            ExamAttempt.exam_session_id
        ).group_by(
            ExamAttempt.candidate_id,
            ExamAttempt.exam_session_id
        ).having(
            func.count(ExamAttempt.id) > 1
        ).all()

        print(f"Found {len(duplicates)} candidates with duplicate attempts.")

        for candidate_id, session_id in duplicates:
            attempts = db.query(ExamAttempt).filter(
                ExamAttempt.candidate_id == candidate_id,
                ExamAttempt.exam_session_id == session_id
            ).all()

            print(f"\nCandidate ID {candidate_id} has {len(attempts)} attempts:")
            
            best_attempt = None
            max_answered = -1

            # Determine the best attempt based on answered count and submission status
            for attempt in attempts:
                answered_count = db.query(CandidateAnswer).filter(
                    CandidateAnswer.attempt_id == attempt.id,
                    CandidateAnswer.selected_option.isnot(None),
                    CandidateAnswer.selected_option != ""
                ).count()
                
                print(f"  Attempt ID {attempt.id}: status={attempt.status}, answered={answered_count}, reopened_from_submitted={attempt.reopened_from_submitted}")
                
                # Decision logic:
                # 1. Higher answered count is better
                # 2. If tie, prefer in_progress/submitted over invalidated_duplicate
                # 3. If tie, prefer reopened_from_submitted = True
                # 4. If tie, prefer higher ID
                is_better = False
                if best_attempt is None:
                    is_better = True
                else:
                    if answered_count > max_answered:
                        is_better = True
                    elif answered_count == max_answered:
                        # Tie-breaker: status priority
                        status_priority = {"submitted": 3, "auto_submitted": 3, "in_progress": 2, "expired": 1, "invalidated_duplicate": 0}
                        curr_priority = status_priority.get(attempt.status, 0)
                        best_priority = status_priority.get(best_attempt.status, 0)
                        if curr_priority > best_priority:
                            is_better = True
                        elif curr_priority == best_priority:
                            # Reopened from submitted priority
                            if attempt.reopened_from_submitted and not best_attempt.reopened_from_submitted:
                                is_better = True
                            elif attempt.reopened_from_submitted == best_attempt.reopened_from_submitted:
                                if attempt.id > best_attempt.id:
                                    is_better = True

                if is_better:
                    best_attempt = attempt
                    max_answered = answered_count

            print(f"  --> Keeping Attempt ID {best_attempt.id} as official.")
            
            # Invalidate all other attempts
            for attempt in attempts:
                if attempt.id != best_attempt.id:
                    attempt.status = "invalidated_duplicate"
                    print(f"  [x] Invalidated Attempt ID {attempt.id}")
            
        db.commit()
        print("\nCleanup completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()