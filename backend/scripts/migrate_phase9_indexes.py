import os
import sys
from sqlalchemy import inspect, text

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
import app.models  # Registers all models

def get_existing_indexes(inspector, table_name):
    try:
        indexes = inspector.get_indexes(table_name)
        return [idx['name'] for idx in indexes]
    except Exception as e:
        print(f"Error fetching indexes for table {table_name}: {str(e)}")
        return []

def get_existing_unique_constraints(inspector, table_name):
    try:
        constraints = inspector.get_unique_constraints(table_name)
        return [c['name'] for c in constraints]
    except Exception as e:
        print(f"Error fetching unique constraints for table {table_name}: {str(e)}")
        return []

def add_index_if_missing(connection, table_name, column_name, index_name, existing_indexes):
    if index_name in existing_indexes:
        print(f"Index '{index_name}' already exists on '{table_name}'. Skipping.")
        return
        
    print(f"Creating index '{index_name}' on '{table_name}({column_name})'...")
    try:
        connection.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({column_name});"))
        print(f"Index '{index_name}' created successfully.")
    except Exception as e:
        print(f"Error creating index '{index_name}': {str(e)}")

def run_migration():
    print("Starting database index optimization for Phase 9...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Required tables mapping
    required_tables = ["candidates", "questions", "exam_attempts", "candidate_answers", "departments", "exam_sessions"]
    for t in required_tables:
        if t not in tables:
            print(f"Warning: Table '{t}' does not exist. Skipping index optimization.")
            return

    with engine.begin() as connection:
        # Define recommended indexes
        index_configs = [
            # candidates
            ("candidates", "department_id", "ix_candidates_department_id"),
            ("candidates", "exam_session_id", "ix_candidates_exam_session_id"),
            ("candidates", "is_active", "ix_candidates_is_active"),
            ("candidates", "photo_status", "ix_candidates_photo_status"),
            
            # questions
            ("questions", "department_id", "ix_questions_department_id"),
            ("questions", "is_active", "ix_questions_is_active"),
            ("questions", "question_no", "ix_questions_question_no"),
            
            # exam_attempts
            ("exam_attempts", "candidate_id", "ix_exam_attempts_candidate_id"),
            ("exam_attempts", "department_id", "ix_exam_attempts_department_id"),
            ("exam_attempts", "exam_session_id", "ix_exam_attempts_exam_session_id"),
            ("exam_attempts", "status", "ix_exam_attempts_status"),
            ("exam_attempts", "submitted_time", "ix_exam_attempts_submitted_time"),
            ("exam_attempts", "score", "ix_exam_attempts_score"),
            ("exam_attempts", "result_status", "ix_exam_attempts_result_status"),
            
            # candidate_answers
            ("candidate_answers", "attempt_id", "ix_candidate_answers_attempt_id"),
            ("candidate_answers", "question_id", "ix_candidate_answers_question_id"),
            ("candidate_answers", "candidate_id", "ix_candidate_answers_candidate_id"),
            ("candidate_answers", "answer_status", "ix_candidate_answers_answer_status"),
            
            # departments
            ("departments", "department_code", "ix_departments_department_code"),
            ("departments", "department_name", "ix_departments_department_name"),
            ("departments", "is_active", "ix_departments_is_active"),
            
            # exam_sessions
            ("exam_sessions", "exam_date", "ix_exam_sessions_exam_date"),
            ("exam_sessions", "start_time", "ix_exam_sessions_start_time"),
            ("exam_sessions", "end_time", "ix_exam_sessions_end_time"),
            ("exam_sessions", "is_active", "ix_exam_sessions_is_active")
        ]

        # Apply indexes
        for table, col, idx_name in index_configs:
            existing = get_existing_indexes(inspector, table)
            add_index_if_missing(connection, table, col, idx_name, existing)
            
    print("Database index optimization completed successfully!")

if __name__ == "__main__":
    run_migration()
