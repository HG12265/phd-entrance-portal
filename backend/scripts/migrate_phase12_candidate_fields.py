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
    print("Starting database migration for Phase 12...")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'candidates' not in tables:
        print("Error: Table 'candidates' does not exist yet. Please initialize DB first.")
        return

    with engine.begin() as connection:
        candidate_columns = [col['name'] for col in inspector.get_columns('candidates')]
        
        candidates_adds = {
            "application_id": "VARCHAR(191) NULL",
            "applicant_name": "VARCHAR(191) NULL",
            "initial": "VARCHAR(50) NULL",
            "category_ft_pt": "VARCHAR(50) NULL",
            "programme_offered": "VARCHAR(191) NULL",
            "subject": "VARCHAR(191) NULL",
            "original_department_text": "VARCHAR(191) NULL"
        }
        
        for col_name, col_def in candidates_adds.items():
            if col_name not in candidate_columns:
                print(f"Adding column '{col_name}' to 'candidates' table...")
                connection.execute(text(f"ALTER TABLE candidates ADD COLUMN {col_name} {col_def};"))
                print(f"Column '{col_name}' added successfully.")
            else:
                print(f"Column '{col_name}' already exists in 'candidates' table.")
                
        # Populate existing rows with application_number where application_id is null
        print("Populating application_id and applicant_name for existing records...")
        connection.execute(text(
            "UPDATE candidates SET application_id = application_number WHERE application_id IS NULL;"
        ))
        connection.execute(text(
            "UPDATE candidates SET applicant_name = name WHERE applicant_name IS NULL;"
        ))
        print("Existing records populated.")
        
        # Verify duplicate application_ids before adding unique index
        duplicates_check = connection.execute(text(
            "SELECT application_id, COUNT(*) FROM candidates WHERE application_id IS NOT NULL GROUP BY application_id HAVING COUNT(*) > 1;"
        )).fetchall()
        
        if duplicates_check:
            print("WARNING: Duplicate application_id found. Unique index cannot be added safely:")
            for row in duplicates_check:
                print(f"Duplicate Application ID: {row[0]} (Count: {row[1]})")
        else:
            # Add unique index if safe and not already existing
            existing_indexes = get_existing_indexes(inspector, 'candidates')
            idx_name = "ix_candidates_application_id"
            if idx_name not in existing_indexes:
                print(f"Adding unique index '{idx_name}' to candidates(application_id)...")
                connection.execute(text(
                    f"CREATE UNIQUE INDEX {idx_name} ON candidates (application_id);"
                ))
                print("Unique index added successfully.")
            else:
                print(f"Unique index '{idx_name}' already exists on 'candidates'.")
                
    print("Database migration for Phase 12 completed successfully!")

if __name__ == "__main__":
    run_migration()
