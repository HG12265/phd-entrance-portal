import os
import sys
from sqlalchemy import inspect, text

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
import app.models  # Registers all models

def run_migration():
    print("Starting database migration for Phase 7...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'exam_attempts' not in tables or 'candidate_answers' not in tables:
        print("Warning: Required tables 'exam_attempts' or 'candidate_answers' do not exist yet. Running Base.metadata.create_all...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
        return

    with engine.begin() as connection:
        # 1. Update exam_attempts columns
        attempt_columns = [col['name'] for col in inspector.get_columns('exam_attempts')]
        
        exam_attempts_adds = {
            "score": "INT DEFAULT 0 NOT NULL",
            "correct_count": "INT DEFAULT 0 NOT NULL",
            "wrong_count": "INT DEFAULT 0 NOT NULL",
            "unanswered_count": "INT DEFAULT 0 NOT NULL",
            "result_status": "VARCHAR(10) NULL",
            "submission_type": "VARCHAR(20) NULL",
            "evaluated_at": "DATETIME NULL"
        }
        
        for col_name, col_def in exam_attempts_adds.items():
            if col_name not in attempt_columns:
                print(f"Adding column '{col_name}' to 'exam_attempts' table...")
                connection.execute(text(f"ALTER TABLE exam_attempts ADD COLUMN {col_name} {col_def};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists in 'exam_attempts' table.")

        # 2. Update candidate_answers columns
        answer_columns = [col['name'] for col in inspector.get_columns('candidate_answers')]
        
        candidate_answers_adds = {
            "is_correct": "BOOLEAN NULL",
            "mark_awarded": "INT DEFAULT 0 NOT NULL"
        }
        
        for col_name, col_def in candidate_answers_adds.items():
            if col_name not in answer_columns:
                print(f"Adding column '{col_name}' to 'candidate_answers' table...")
                connection.execute(text(f"ALTER TABLE candidate_answers ADD COLUMN {col_name} {col_def};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists in 'candidate_answers' table.")
                
    print("Database migration for Phase 7 completed successfully!")

if __name__ == "__main__":
    run_migration()
