import os
import sys

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.department import Department
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.exam_attempt import ExamAttempt
from app.models.candidate_answer import CandidateAnswer
from sqlalchemy import or_

KEEP_NAMES = {
    "Biochemistry",
    "Biotechnology",
    "Microbiology",
    "Computer Science",
    "Library and Information Science",
    "Mathematics",
    "Statistics",
    "Physics",
    "Chemistry",
    "Geology",
    "Commerce",
    "Economics",
    "Management Studies",
    "English",
    "Tamil",
    "Education",
    "Food Science and Nutrition",
    "Textiles and Apparel Design",
    "Sociology",
    "Psychology",
    "Journalism and Mass Communication",
    "History",
    "Botany",
    "Zoology",
    "Nutrition and Dietetics",
    "Sciences",
    "Energy Science and Technology",
    "Environmental Science"
}

def cleanup():
    db = SessionLocal()
    try:
        # 1. Rename any close matches before deletion check
        lib_sci = db.query(Department).filter(Department.department_name == "Library Science").first()
        if lib_sci:
            lib_sci.department_name = "Library and Information Science"
            lib_sci.department_code = "LIS"
            db.commit()
            print("Renamed 'Library Science' to 'Library and Information Science'")

        # Fetch all departments
        all_depts = db.query(Department).all()
        depts_to_delete = []
        for d in all_depts:
            if d.department_name not in KEEP_NAMES:
                depts_to_delete.append(d)

        print(f"Found {len(depts_to_delete)} departments to permanently delete.")

        for dept in depts_to_delete:
            department_id = dept.id
            print(f"Purging department '{dept.department_name}' (ID: {department_id})...")

            # 1. Candidate IDs in department
            cand_ids = [c.id for c in db.query(Candidate.id).filter(Candidate.department_id == department_id).all()]
            
            # 2. Attempt IDs of candidates in department
            attempt_ids_cand = [a.id for a in db.query(ExamAttempt.id).filter(ExamAttempt.candidate_id.in_(cand_ids)).all()] if cand_ids else []
            
            # 3. Question IDs in department
            question_ids = [q.id for q in db.query(Question.id).filter(Question.department_id == department_id).all()]

            # Delete answers
            answers_deleted = 0
            if attempt_ids_cand or question_ids:
                answers_deleted = db.query(CandidateAnswer).filter(
                    or_(
                        CandidateAnswer.attempt_id.in_(attempt_ids_cand) if attempt_ids_cand else False,
                        CandidateAnswer.question_id.in_(question_ids) if question_ids else False
                    )
                ).delete(synchronize_session=False)

            # Delete attempts
            attempts_deleted = db.query(ExamAttempt).filter(
                or_(
                    ExamAttempt.candidate_id.in_(cand_ids) if cand_ids else False,
                    ExamAttempt.department_id == department_id
                )
            ).delete(synchronize_session=False)

            # Delete candidates
            candidates_deleted = db.query(Candidate).filter(Candidate.department_id == department_id).delete(synchronize_session=False)

            # Delete questions
            questions_deleted = db.query(Question).filter(Question.department_id == department_id).delete(synchronize_session=False)

            # Delete department row
            db.query(Department).filter(Department.id == department_id).delete(synchronize_session=False)

            print(f"Deleted '{dept.department_name}': answers={answers_deleted}, attempts={attempts_deleted}, candidates={candidates_deleted}, questions={questions_deleted}")

        db.commit()
        print("Department cleanup successfully completed!")
    except Exception as e:
        db.rollback()
        print(f"Failed to clean up departments: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
