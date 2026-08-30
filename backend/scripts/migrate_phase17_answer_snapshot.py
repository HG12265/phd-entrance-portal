#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.database import SessionLocal, engine

def run_migration():
    print("Phase 17 Migration: Answer Snapshot Columns")
    with engine.connect() as conn:
        res = conn.execute(text("SHOW COLUMNS FROM exam_attempts"))
        existing = {row[0] for row in res}
        print(f"Current columns: {len(existing)}")
        added = []
        if "last_answer_snapshot_json" not in existing:
            conn.execute(text("ALTER TABLE exam_attempts ADD COLUMN last_answer_snapshot_json LONGTEXT NULL"))
            added.append("last_answer_snapshot_json")
            print("  [+] Added: last_answer_snapshot_json")
        else:
            print("  [skip] last_answer_snapshot_json already exists")
        if "selected_count_at_submit" not in existing:
            conn.execute(text("ALTER TABLE exam_attempts ADD COLUMN selected_count_at_submit INT NULL"))
            added.append("selected_count_at_submit")
            print("  [+] Added: selected_count_at_submit")
        else:
            print("  [skip] selected_count_at_submit already exists")
        conn.commit()
    print(f"Done. Added: {added}")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)