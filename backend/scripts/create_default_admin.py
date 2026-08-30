import os
import sys

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import Base, AdminUser, SystemSetting
from app.utils.security import hash_password

import time

def create_default_admin():
    # Ensure all tables exist (importing Base from app.models registers all schemas)
    print("Ensuring database tables are created...")
    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database tables created/verified successfully.")
            break
        except Exception as err:
            if attempt == max_retries:
                print(f"Failed to connect to database after {max_retries} attempts: {err}")
                raise err
            print(f"Database not ready yet (attempt {attempt}/{max_retries}): {err}. Retrying in 2 seconds...")
            time.sleep(2)
    
    # Read environment variables
    admin_name = os.getenv("DEFAULT_ADMIN_NAME", "Super Admin")
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@phdportal.com")
    admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "MCA2026")  # Default password if not set in .env
    
    db = SessionLocal()
    try:
        # Auto-migration: Check if 'image_path' column exists in 'questions' table
        from sqlalchemy import text
        try:
            db.execute(text("SELECT image_path FROM questions LIMIT 1"))
        except Exception:
            print("Migration: Adding 'image_path' column to 'questions' table...")
            try:
                db.execute(text("ALTER TABLE questions ADD COLUMN image_path VARCHAR(500) NULL"))
                db.commit()
                print("Migration: 'image_path' column added successfully.")
            except Exception as migration_err:
                print(f"Migration warning (might already exist): {migration_err}")
                db.rollback()

        # Check if super admin already exists
        existing_admin = db.query(AdminUser).filter(AdminUser.email == admin_email).first()
        if not existing_admin:
            # Create new default super admin
            hashed = hash_password(admin_password)
            new_admin = AdminUser(
                name=admin_name,
                email=admin_email,
                password_hash=hashed,
                role="super_admin",
                is_active=True
            )
            db.add(new_admin)
            print(f"Successfully created default super admin user:")
            print(f"  Name:     {admin_name}")
            print(f"  Email:    {admin_email}")
            print(f"  Password: [Configured in .env]")
        else:
            print(f"Super admin user with email '{admin_email}' already exists.")

        # Check if staff admin already exists
        staff_email = "staff@phdportal.com"
        existing_staff = db.query(AdminUser).filter(AdminUser.email == staff_email).first()
        if not existing_staff:
            # Create new default staff admin
            hashed_staff = hash_password("MCA2026")
            new_staff = AdminUser(
                name="Staff Admin",
                email=staff_email,
                password_hash=hashed_staff,
                role="staff_admin",
                is_active=True
            )
            db.add(new_staff)
            print(f"Successfully created default staff admin user:")
            print(f"  Name:     Staff Admin")
            print(f"  Email:    {staff_email}")
            print(f"  Password: MCA2026")
        else:
            print(f"Staff admin user with email '{staff_email}' already exists.")

        # Seed default system settings
        default_settings = {
            "portal_title": "PhD Admission Entrance"
        }
        for k, v in default_settings.items():
            existing_set = db.query(SystemSetting).filter(SystemSetting.key == k).first()
            if not existing_set:
                new_set = SystemSetting(key=k, value=v)
                db.add(new_set)
                print(f"Seeded default setting: {k} = '{v}'")
            else:
                print(f"Setting '{k}' already exists.")

        db.commit()
        
        # Seed default departments
        try:
            from scripts.seed_departments import seed as seed_departments
            print("Seeding default departments...")
            seed_departments()
        except Exception as seed_err:
            print(f"Error seeding default departments: {seed_err}")

    except Exception as e:
        print(f"Error creating default admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_default_admin()
