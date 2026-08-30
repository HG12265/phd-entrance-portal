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

def run_migration():
    print("Starting database migration for Phase 14...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'exam_attempts' not in tables:
        print("Error: Table 'exam_attempts' does not exist yet. Please initialize DB first.")
        return

    with engine.begin() as connection:
        # 1. Update columns in exam_attempts table
        attempt_columns = [col['name'] for col in inspector.get_columns('exam_attempts')]
        
        attempt_adds = {
            "remaining_seconds_at_submit": "INT NULL",
            "submitted_reopen_count": "INT NOT NULL DEFAULT 0",
            "submitted_reopened_at": "DATETIME NULL",
            "submitted_reopened_by_admin_id": "INT NULL",
            "submitted_reopen_reason": "TEXT NULL",
            "reopened_from_submitted": "TINYINT(1) NOT NULL DEFAULT 0"
        }
        
        for col_name, col_def in attempt_adds.items():
            if col_name not in attempt_columns:
                print(f"Adding column '{col_name}' to 'exam_attempts' table...")
                connection.execute(text(f"ALTER TABLE exam_attempts ADD COLUMN {col_name} {col_def};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists in 'exam_attempts' table.")
                
        # 2. Check and create exam_attempt_reopen_audits table
        if 'exam_attempt_reopen_audits' not in tables:
            print("Creating 'exam_attempt_reopen_audits' table...")
            connection.execute(text("""
                CREATE TABLE exam_attempt_reopen_audits (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    attempt_id INT NOT NULL,
                    candidate_id INT NOT NULL,
                    admin_id INT NOT NULL,
                    reopen_type VARCHAR(50) NOT NULL,
                    old_status VARCHAR(50) NOT NULL,
                    new_status VARCHAR(50) NOT NULL,
                    old_end_time DATETIME NULL,
                    new_end_time DATETIME NULL,
                    remaining_seconds_granted INT NULL,
                    reason TEXT NULL,
                    old_submitted_time DATETIME NULL,
                    old_score INT NULL,
                    old_result_status VARCHAR(50) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
                    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
                    FOREIGN KEY (admin_id) REFERENCES admin_users(id) ON DELETE CASCADE,
                    INDEX ix_reopen_audits_attempt_id (attempt_id),
                    INDEX ix_reopen_audits_candidate_id (candidate_id),
                    INDEX ix_reopen_audits_admin_id (admin_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            print("'exam_attempt_reopen_audits' table created successfully.")
        else:
            print("Table 'exam_attempt_reopen_audits' already exists.")
            
    print("Database migration for Phase 14 completed successfully!")

if __name__ == "__main__":
    run_migration()
