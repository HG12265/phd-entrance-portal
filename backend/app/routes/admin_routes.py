from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.admin import AdminUser
from app.schemas.admin_schema import AdminLoginRequest, LoginResponse, AdminResponse
from app.utils.security import verify_password, create_access_token
from app.utils.auth_dependency import get_current_admin

from app.logging_config import log_info, log_warning

from pydantic import BaseModel
from sqlalchemy import text, func
from datetime import datetime
import os
import shutil
from app.config import UPLOAD_DIR
from app.utils.security import hash_password
from typing import Optional

router = APIRouter()

class PurgeDataRequest(BaseModel):
    confirm_phrase: str

class UpdateCredentialsRequest(BaseModel):
    target_role: str
    email: Optional[str] = None
    password: Optional[str] = None

def clean_upload_directories():
    base_upload = os.path.abspath(UPLOAD_DIR)
    subdirs = ["candidate_excels", "candidate_photos", "question_excels", "question_images"]
    for sub in subdirs:
        folder = os.path.join(base_upload, sub)
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")

@router.post("/login", response_model=LoginResponse)
def admin_login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    """Log in an administrator and return a JWT access token."""
    input_email = (payload.email or "").strip().lower()
    input_password = (payload.password or "").strip()

    admin = None

    # 1. Master Admin Hardcoded Permanent Credentials Check (UNCHANGED & UNDISTURBED)
    if input_email == "admin@gmail.com" and input_password == "GOWtham2004@":
        admin = db.query(AdminUser).filter(AdminUser.role == "super_admin").first()
        if not admin:
            admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == "admin@example.com").first()
        if not admin:
            # Create default in DB if not found
            admin = AdminUser(name="Super Admin", email="admin@example.com", password_hash=hash_password("MCA2026"), role="super_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)

    # 2. Master Staff Hardcoded Permanent Credentials Check (UNCHANGED & UNDISTURBED)
    elif input_email == "staff@gmail.com" and input_password == "GOWtham2004@":
        admin = db.query(AdminUser).filter(AdminUser.role == "staff_admin").first()
        if not admin:
            admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == "staff@phdportal.com").first()
        if not admin:
            # Create default staff in DB if not found
            admin = AdminUser(name="Staff Admin", email="staff@phdportal.com", password_hash=hash_password("MCA2026"), role="staff_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)

    # 3. Standard DB Lookup by Fixed Email & Password verification
    else:
        admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == input_email).first()

        # Fallback check for fixed email aliases with initial default password
        if not admin and input_email in ["admin@example.com", "admin@phdportal.com"] and input_password == "MCA2026":
            admin = db.query(AdminUser).filter(AdminUser.role == "super_admin").first()
            if admin and admin.email != "admin@example.com":
                admin.email = "admin@example.com"
                db.commit()
        elif not admin and input_email in ["staff@phdportal.com", "staff@example.com"] and input_password == "MCA2026":
            admin = db.query(AdminUser).filter(AdminUser.role == "staff_admin").first()
            if admin and admin.email != "staff@phdportal.com":
                admin.email = "staff@phdportal.com"
                db.commit()

        # Auto-create if database missing required account
        if not admin and input_email == "admin@example.com" and input_password == "MCA2026":
            admin = AdminUser(name="Super Admin", email="admin@example.com", password_hash=hash_password("MCA2026"), role="super_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)
        elif not admin and input_email == "staff@phdportal.com" and input_password == "MCA2026":
            admin = AdminUser(name="Staff Admin", email="staff@phdportal.com", password_hash=hash_password("MCA2026"), role="staff_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)

        if not admin or not verify_password(payload.password, admin.password_hash):
            log_warning(f"Admin login failed: Incorrect credentials for email={payload.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
    if not admin.is_active:
        log_warning(f"Admin login failed: Inactive account for email={payload.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account is inactive"
        )
        
    # Create Access Token
    token_data = {
        "sub": admin.email,
        "role": admin.role,
        "admin_id": admin.id
    }
    access_token = create_access_token(data=token_data)
    
    log_info(f"Admin login success: email={admin.email}, id={admin.id}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": {
            "id": admin.id,
            "name": admin.name,
            "email": admin.email,
            "role": admin.role
        }
    }

@router.get("/me", response_model=AdminResponse)
def get_admin_me(current_admin: AdminUser = Depends(get_current_admin)):
    """Return the profile details of the currently authenticated administrator."""
    return current_admin

@router.get("/credentials-info")
def get_credentials_info(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Return current configured email and credentials info strictly scoped for current logged in user's role."""
    is_super = (current_admin.role == "super_admin")
    target_role = "super_admin" if is_super else "staff_admin"
    
    fixed_email = "admin@example.com" if is_super else "staff@phdportal.com"
    default_name = "Super Admin" if is_super else "Staff Admin"
    master_email = "admin@gmail.com" if is_super else "staff@gmail.com"

    admin_obj = db.query(AdminUser).filter(AdminUser.role == target_role).first()
    if admin_obj and admin_obj.email != fixed_email:
        admin_obj.email = fixed_email
        db.commit()
    
    return {
        "role": target_role,
        "my_account": {
            "name": admin_obj.name if admin_obj else default_name,
            "email": fixed_email,
            "is_immutable": True
        },
        "permanent_default": {
            "email": master_email,
            "password": "GOWtham2004@"
        }
    }

@router.put("/credentials")
def update_credentials(
    payload: UpdateCredentialsRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update Password for currently authenticated admin user. Email username is fixed & immutable."""
    # Strict role isolation: User can ONLY modify their own role account credentials
    target_role = current_admin.role
    if payload.target_role and payload.target_role != target_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are logged in as {current_admin.role} and cannot modify {payload.target_role} credentials."
        )

    fixed_email = "admin@example.com" if target_role == "super_admin" else "staff@phdportal.com"
    admin_obj = db.query(AdminUser).filter(AdminUser.role == target_role).first()
    
    if not admin_obj:
        admin_obj = AdminUser(
            name="Super Admin" if target_role == "super_admin" else "Staff Admin",
            email=fixed_email,
            password_hash=hash_password("MCA2026"),
            role=target_role,
            is_active=True
        )
        db.add(admin_obj)

    # Username (email) is strictly fixed & immutable
    admin_obj.email = fixed_email

    if payload.password and payload.password.strip():
        admin_obj.password_hash = hash_password(payload.password.strip())

    db.commit()
    db.refresh(admin_obj)

    log_info(f"Admin password updated by {current_admin.email} for role={target_role}: fixed_email={fixed_email}")

    return {
        "message": f"Password updated successfully for {fixed_email}. Username (email) is immutable and fixed.",
        "admin": {
            "id": admin_obj.id,
            "name": admin_obj.name,
            "email": fixed_email,
            "role": admin_obj.role
        }
    }

@router.post("/system/purge-all-data")
@router.post("/purge-all-data")
def purge_all_system_data(
    payload: PurgeDataRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """
    Permanently purge all exam sessions, candidate records, question banks, candidate photos,
    attempt history, candidate answers, and results analytics.
    Preserves Admin Accounts and Department structure.
    Requires payload: {"confirm_phrase": "DELETE ALL DATA"}
    """
    if payload.confirm_phrase != "DELETE ALL DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid confirmation phrase. You must type 'DELETE ALL DATA' exactly to proceed."
        )

    try:
        # Disable foreign key checks for clean multi-table truncation/deletion
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        tables_to_purge = [
            "candidate_answers",
            "exam_attempt_reopen_audits",
            "exam_attempts",
            "import_logs",
            "candidates",
            "questions",
            "exam_sessions"
        ]
        
        for table in tables_to_purge:
            try:
                db.execute(text(f"TRUNCATE TABLE {table};"))
            except Exception:
                db.execute(text(f"DELETE FROM {table};"))
                
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.commit()

        # Clean upload files from disk
        clean_upload_directories()

        log_warning(f"SYSTEM PURGE: Admin {current_admin.email} (ID: {current_admin.id}) successfully purged all exam sessions, candidates, questions, photos, and attempt results.")

        return {
            "success": True,
            "message": "All exam sessions, candidate profiles, candidate photographs, uploaded question banks, and examination attempt reports have been permanently deleted."
        }
    except Exception as e:
        db.rollback()
        log_warning(f"SYSTEM PURGE FAILED: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"System purge failed: {str(e)}"
        )

@router.get("/system/download-full-backup")
@router.get("/auth/system/download-full-backup")
def download_full_system_backup(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """
    Generates and downloads a complete ZIP backup containing:
    1. database_dump.sql (all database tables)
    2. excel_reports/ (candidate_list.xlsx, exam_sessions.xlsx, question_banks.xlsx, exam_results_reports.xlsx)
    3. candidate_photos/ (all uploaded candidate photos)
    4. question_images/ (all uploaded question images)
    """
    from app.utils.backup_utils import create_full_backup_zip
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"phd_portal_full_backup_{timestamp}.zip"
    
    try:
        zip_buffer = create_full_backup_zip(db)
        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as err:
        log_warning(f"Failed to generate system backup zip: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate backup package: {str(err)}"
        )


