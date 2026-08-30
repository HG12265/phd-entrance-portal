import os
import sys
from sqlalchemy import inspect, text

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
import app.models  # Registers all models

def run_migration():
    print("Starting database migration for Phase 6...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    old_schema_detected = False
    
    if 'exam_attempts' in tables:
        columns = [col['name'] for col in inspector.get_columns('exam_attempts')]
        if 'exam_id' in columns:
            print("Old incompatible 'exam_attempts' schema detected (found 'exam_id' column instead of 'exam_session_id').")
            old_schema_detected = True
            
    if old_schema_detected:
        with engine.begin() as connection:
            # Check row count
            attempts_count = connection.execute(text("SELECT COUNT(*) FROM exam_attempts")).scalar() or 0
            answers_count = 0
            if 'candidate_answers' in tables:
                answers_count = connection.execute(text("SELECT COUNT(*) FROM candidate_answers")).scalar() or 0
                
            if attempts_count > 0 or answers_count > 0:
                print(f"Old tables contain data (attempts: {attempts_count}, answers: {answers_count}). Creating backups...")
                connection.execute(text("DROP TABLE IF EXISTS exam_attempts_backup_v5;"))
                connection.execute(text("CREATE TABLE exam_attempts_backup_v5 AS SELECT * FROM exam_attempts;"))
                if 'candidate_answers' in tables:
                    connection.execute(text("DROP TABLE IF EXISTS candidate_answers_backup_v5;"))
                    connection.execute(text("CREATE TABLE candidate_answers_backup_v5 AS SELECT * FROM candidate_answers;"))
                print("Backup tables created successfully: 'exam_attempts_backup_v5' and 'candidate_answers_backup_v5'.")
            else:
                print("Old tables are empty. Safe to recreate without backup.")
                
            print("Dropping old candidate_answers and exam_attempts tables...")
            connection.execute(text("DROP TABLE IF EXISTS candidate_answers;"))
            connection.execute(text("DROP TABLE IF EXISTS exam_attempts;"))
            print("Old tables dropped successfully.")
            
    # Recreate tables safely
    print("Running Base.metadata.create_all to ensure updated tables exist...")
    Base.metadata.create_all(bind=engine)
    print("ExamAttempt and CandidateAnswer tables checks completed.")
    print("Database migration for Phase 6 completed successfully!")

if __name__ == "__main__":
    run_migration()
