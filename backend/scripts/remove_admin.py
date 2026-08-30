import os
import sys

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import AdminUser

def remove_admin():
    # Read environment variable for default admin email
    admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    
    print(f"Connecting to database to remove admin credentials...")
    db = SessionLocal()
    try:
        # Check and remove the admin user configured in .env
        admin = db.query(AdminUser).filter(AdminUser.email == admin_email).first()
        if admin:
            print(f"Found admin user: {admin.name} ({admin.email})")
            db.delete(admin)
            db.commit()
            print(f"Successfully removed admin user with email '{admin_email}' from the database.")
        else:
            print(f"No admin user found with the configured email '{admin_email}'.")

        # Check if other admin users exist
        all_admins = db.query(AdminUser).all()
        if all_admins:
            print(f"\nRemaining admin users in database ({len(all_admins)}):")
            for a in all_admins:
                print(f"  - {a.name} ({a.email}, Role: {a.role})")
            
            # If the user passed '--all' argument, clear everyone
            if len(sys.argv) > 1 and sys.argv[1] == "--all":
                print("\nRemoving ALL remaining admin users...")
                deleted_count = db.query(AdminUser).delete()
                db.commit()
                print(f"Successfully deleted {deleted_count} admin user(s).")
            else:
                print("\nTo remove ALL admin users in the database, run:")
                print("python scripts/remove_admin.py --all")
        else:
            print("\nNo admin users left in the database.")

    except Exception as e:
        print(f"Error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    remove_admin()
