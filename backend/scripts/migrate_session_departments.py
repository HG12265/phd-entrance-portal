#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.database import engine

def run_migration():
    print("Migration: Session Department Association Table")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS session_department_association (
                session_id INT NOT NULL,
                department_id INT NOT NULL,
                PRIMARY KEY (session_id, department_id),
                FOREIGN KEY (session_id) REFERENCES exam_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """))
        conn.commit()
    print("Done creating session_department_association table.")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
