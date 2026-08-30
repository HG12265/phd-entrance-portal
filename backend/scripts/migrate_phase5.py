import os
import sys
from sqlalchemy import inspect, text

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
import app.models  # Registers all models

def run_migration():
    print("Starting database migration for Phase 5...")
    
    # 1. Ensure new tables (exam_sessions) are created
    print("Creating tables (if not already existing)...")
    Base.metadata.create_all(bind=engine)
    print("Base tables check completed.")
    
    # 2. Inspect candidates table
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('candidates')]
    
    with engine.begin() as connection:
        # Check if exam_session_id column exists
        if 'exam_session_id' not in columns:
            print("Column 'exam_session_id' is missing in 'candidates' table. Adding column...")
            connection.execute(text("ALTER TABLE candidates ADD COLUMN exam_session_id INT NULL;"))
            print("Successfully added column 'exam_session_id' to 'candidates' table.")
        else:
            print("Column 'exam_session_id' already exists in 'candidates' table.")
            
        # Check if foreign key constraint exists
        fkeys = inspector.get_foreign_keys('candidates')
        fk_exists = any(fk['referred_table'] == 'exam_sessions' for fk in fkeys)
        
        if not fk_exists:
            print("Foreign key constraint linking 'candidates' to 'exam_sessions' is missing. Creating constraint...")
            connection.execute(text(
                "ALTER TABLE candidates ADD CONSTRAINT fk_candidates_exam_sessions "
                "FOREIGN KEY (exam_session_id) REFERENCES exam_sessions(id) ON DELETE SET NULL;"
            ))
            print("Successfully added foreign key constraint 'fk_candidates_exam_sessions' to 'candidates' table.")
        else:
            print("Foreign key constraint linking 'candidates' to 'exam_sessions' already exists.")
            
    print("Database migration for Phase 5 completed successfully!")

if __name__ == "__main__":
    run_migration()
