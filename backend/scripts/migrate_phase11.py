import os
import sys
from sqlalchemy import inspect, text

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
import app.models  # Registers all models

def run_migration():
    print("Starting database migration for Phase 11...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'exam_attempts' not in tables:
        print("Warning: Table 'exam_attempts' does not exist yet. Running Base.metadata.create_all...")
        Base.metadata.create_all(bind=engine)
        print("Tables created.")
        return

    with engine.begin() as connection:
        attempt_columns = [col['name'] for col in inspector.get_columns('exam_attempts')]
        
        exam_attempts_adds = {
            "active_lock_token": "VARCHAR(191) NULL",
            "lock_status": "VARCHAR(50) DEFAULT 'unlocked' NOT NULL",
            "locked_at": "DATETIME NULL",
            "reopened_at": "DATETIME NULL",
            "reopened_by_admin_id": "INT NULL",
            "reopen_reason": "TEXT NULL",
            "reopen_count": "INT DEFAULT 0 NOT NULL",
            "last_client_fingerprint": "VARCHAR(191) NULL"
        }
        
        for col_name, col_def in exam_attempts_adds.items():
            if col_name not in attempt_columns:
                print(f"Adding column '{col_name}' to 'exam_attempts' table...")
                connection.execute(text(f"ALTER TABLE exam_attempts ADD COLUMN {col_name} {col_def};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists in 'exam_attempts' table.")
                
    print("Database migration for Phase 11 completed successfully!")

if __name__ == "__main__":
    run_migration()
