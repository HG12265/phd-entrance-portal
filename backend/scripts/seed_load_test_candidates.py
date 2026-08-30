#!/usr/bin/env python3
import sys
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

# Add backend root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.department import Department
from app.models.question import Question
from app.models.exam_session import ExamSession
from app.models.candidate import Candidate
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer

kolkata_tz = ZoneInfo("Asia/Kolkata")

def cleanup(db):
    print("Starting cleanup of load testing seed data...")
    
    # 1. Delete test candidates
    cands = db.query(Candidate).filter(Candidate.application_number.like("CET/PHD/TEST/%")).all()
    cand_ids = [c.id for c in cands]
    
    if cand_ids:
        print(f"Deleting answers and exam attempts for {len(cand_ids)} test candidates...")
        # Delete answers and attempts
        db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id.in_(
            db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(cand_ids))
        )).delete(synchronize_session=False)
        
        db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(cand_ids)).delete(synchronize_session=False)
        db.query(Candidate).filter(Candidate.id.in_(cand_ids)).delete(synchronize_session=False)
    
    # 2. Delete test exam session
    session = db.query(ExamSession).filter(ExamSession.session_name == "Load Test Active Session").first()
    if session:
        print("Deleting load test exam session...")
        db.delete(session)
        
    # 3. Delete test department (will cascade delete questions)
    dept = db.query(Department).filter(Department.department_code == "TEST_LOAD").first()
    if dept:
        print("Deleting load test questions...")
        db.query(Question).filter(Question.department_id == dept.id).delete(synchronize_session=False)
        print("Deleting load test department...")
        db.delete(dept)
        
    db.commit()
    print("Cleanup completed successfully!")

def seed(db):
    print("Starting seeder for 300+ candidate load testing...")
    
    # 0. Automatically clean up leftover exam attempts and responses for test candidates
    print("Clearing any leftover load test attempts and answers to prevent device lockouts...")
    cands_to_clear = db.query(Candidate).filter(Candidate.application_number.like("CET/PHD/TEST/%")).all()
    cand_ids_to_clear = [c.id for c in cands_to_clear]
    if cand_ids_to_clear:
        db.query(CandidateAnswer).filter(CandidateAnswer.attempt_id.in_(
            db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(cand_ids_to_clear))
        )).delete(synchronize_session=False)
        db.query(ExamAttempt).filter(ExamAttempt.candidate_id.in_(cand_ids_to_clear)).delete(synchronize_session=False)
        db.commit()

    # 1. Create or fetch test department
    dept = db.query(Department).filter(Department.department_code == "TEST_LOAD").first()
    if not dept:
        dept = Department(
            department_name="Test Load Dept",
            department_code="TEST_LOAD",
            is_active=True
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)
    print(f"Test Department active: ID {dept.id}")
    
    # 2. Add exactly 70 questions for this department (required to start exam)
    q_count = db.query(Question).filter(Question.department_id == dept.id).count()
    if q_count < 70:
        print(f"Currently have {q_count} questions. Seeding to reach exactly 70...")
        # Clear existing ones first to ensure sequential numbers
        db.query(Question).filter(Question.department_id == dept.id).delete()
        
        for i in range(1, 71):
            q = Question(
                department_id=dept.id,
                question_no=i,
                question_text=f"What is the output/result of stress simulation query value number {i}?",
                option_a=f"Option A - simulated response {i}",
                option_b=f"Option B - simulated response {i}",
                option_c=f"Option C - simulated response {i}",
                option_d=f"Option D - simulated response {i}",
                correct_option="A",
                marks=1,
                is_active=True
            )
            db.add(q)
        db.commit()
        print("Successfully seeded 70 questions.")
    else:
        print("70 questions already exist for this department.")
        
    # 3. Create or update active live exam session
    now = datetime.now(kolkata_tz)
    session = db.query(ExamSession).filter(ExamSession.session_name == "Load Test Active Session").first()
    if session:
        print("Updating existing load test active session times...")
        session.exam_date = now.date()
        session.start_time = (now - timedelta(minutes=10)).replace(tzinfo=None)
        session.end_time = (now + timedelta(hours=2)).replace(tzinfo=None)
        session.is_active = True
        if dept not in session.departments:
            session.departments.append(dept)
    else:
        print("Creating new load test active session...")
        session = ExamSession(
            session_name="Load Test Active Session",
            exam_title="PhD Entrance Load Test",
            exam_date=now.date(),
            start_time=(now - timedelta(minutes=10)).replace(tzinfo=None),
            end_time=(now + timedelta(hours=2)).replace(tzinfo=None),
            duration_minutes=120,
            is_active=True,
            departments=[dept]
        )
        db.add(session)
    db.commit()
    db.refresh(session)
    print(f"Active Live Session ready: ID {session.id} ('{session.session_name}')")
    
    # 4. Create 600 test candidates (CET/PHD/TEST/0001 to CET/PHD/TEST/0600)
    print("Checking and seeding 600 candidates...")
    existing_cands = db.query(Candidate).filter(Candidate.application_number.like("CET/PHD/TEST/%")).count()
    if existing_cands < 600:
        for i in range(1, 601):
            app_no = f"CET/PHD/TEST/{i:04d}"
            cand = db.query(Candidate).filter(Candidate.application_number == app_no).first()
            if not cand:
                cand = Candidate(
                    application_number=app_no,
                    name=f"Load Test Candidate {i}",
                    dob=date(2004, 1, 1),
                    applied_subject="Test Load Dept",
                    department_id=dept.id,
                    exam_session_id=session.id,
                    is_active=True
                )
                db.add(cand)
        db.commit()
        print("Successfully seeded 600 test candidates.")
    else:
        # Update their session IDs in case session changed
        cands = db.query(Candidate).filter(Candidate.application_number.like("CET/PHD/TEST/%")).all()
        for cand in cands:
            cand.exam_session_id = session.id
            cand.department_id = dept.id
        db.commit()
        print("600 test candidates already exist. Synced their session and department mapping.")
        
    print("\nSeeding completed successfully! You are ready to run the Locust load test.")
    print("Command to run Locust:")
    print("  locust -f load_tests/locustfile.py --host=http://localhost:8000")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--cleanup":
            cleanup(db)
        else:
            seed(db)
    finally:
        db.close()
