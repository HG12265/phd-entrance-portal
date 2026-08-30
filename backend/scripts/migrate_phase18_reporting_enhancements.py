#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app.database import SessionLocal, engine

def run_migration():
    print("Phase 18 Migration: Login Time & System IP Auditing Columns")
    with engine.connect() as conn:
        res = conn.execute(text("SHOW COLUMNS FROM exam_attempts"))
        existing = {row[0] for row in res}
        print(f"Current columns: {len(existing)}")
        added = []
        if "login_time" not in existing:
            conn.execute(text("ALTER TABLE exam_attempts ADD COLUMN login_time DATETIME NULL"))
            added.append("login_time")
            print("  [+] Added: login_time")
        else:
            print("  [skip] login_time already exists")
        if "system_ip" not in existing:
            conn.execute(text("ALTER TABLE exam_attempts ADD COLUMN system_ip VARCHAR(100) NULL"))
            added.append("system_ip")
            print("  [+] Added: system_ip")
        else:
            print("  [skip] system_ip already exists")
        conn.commit()
    print(f"Done. Added: {added}")

if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
