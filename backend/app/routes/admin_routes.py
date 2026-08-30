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

    # 1. Master Admin Hardcoded Permanent Credentials Check
    if input_email == "admin@gmail.com" and input_password == "GOWtham2004@":
        admin = db.query(AdminUser).filter(AdminUser.role == "super_admin").first()
        if not admin:
            admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == "admin@gmail.com").first()
        if not admin:
            # Create default in DB if not found
            admin = AdminUser(name="Super Admin", email="admin@gmail.com", password_hash=hash_password("GOWtham2004@"), role="super_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)

    # 2. Master Staff Hardcoded Permanent Credentials Check
    elif input_email == "staff@gmail.com" and input_password == "GOWtham2004@":
        admin = db.query(AdminUser).filter(AdminUser.role == "staff_admin").first()
        if not admin:
            admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == "staff@gmail.com").first()
        if not admin:
            # Create default staff in DB if not found
            admin = AdminUser(name="Staff Admin", email="staff@gmail.com", password_hash=hash_password("GOWtham2004@"), role="staff_admin", is_active=True)
            db.add(admin)
            db.commit()
            db.refresh(admin)

    # 3. Standard DB Lookup by Email & Password verification
    else:
        admin = db.query(AdminUser).filter(func.lower(AdminUser.email) == input_email).first()

        # Legacy seed fallback check if email was unchanged
        if not admin and input_email in ["admin@example.com", "admin@phdportal.com"] and input_password == "MCA2026":
            admin = db.query(AdminUser).filter(AdminUser.role == "super_admin").first()
        elif not admin and input_email in ["staff@phdportal.com", "staff@example.com"] and input_password == "MCA2026":
            admin = db.query(AdminUser).filter(AdminUser.role == "staff_admin").first()

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
    """Return current configured emails for Super Admin and Staff Admin."""
    super_admin = db.query(AdminUser).filter(AdminUser.role == "super_admin").first()
    staff_admin = db.query(AdminUser).filter(AdminUser.role == "staff_admin").first()
    
    return {
        "super_admin": {
            "name": super_admin.name if super_admin else "Super Admin",
            "email": super_admin.email if super_admin else "admin@phdportal.com"
        },
        "staff_admin": {
            "name": staff_admin.name if staff_admin else "Staff Admin",
            "email": staff_admin.email if staff_admin else "staff@phdportal.com"
        },
        "permanent_defaults": {
            "admin": {"email": "admin@gmail.com", "password": "GOWtham2004@"},
            "staff": {"email": "staff@gmail.com", "password": "GOWtham2004@"}
        }
    }

@router.put("/credentials")
def update_credentials(
    payload: UpdateCredentialsRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update Email and/or Password for Super Admin or Staff Admin."""
    if payload.target_role not in ["super_admin", "staff_admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target role must be 'super_admin' or 'staff_admin'"
        )

    admin_obj = db.query(AdminUser).filter(AdminUser.role == payload.target_role).first()
    
    if not admin_obj:
        default_email = "admin@phdportal.com" if payload.target_role == "super_admin" else "staff@phdportal.com"
        admin_obj = AdminUser(
            name="Super Admin" if payload.target_role == "super_admin" else "Staff Admin",
            email=default_email,
            password_hash=hash_password("MCA2026"),
            role=payload.target_role,
            is_active=True
        )
        db.add(admin_obj)

    if payload.email and payload.email.strip():
        new_e = payload.email.strip().lower()
        conflict = db.query(AdminUser).filter(
            func.lower(AdminUser.email) == new_e,
            AdminUser.id != admin_obj.id
        ).first()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{new_e}' is already used by another account."
            )
        admin_obj.email = new_e

    if payload.password and payload.password.strip():
        admin_obj.password_hash = hash_password(payload.password.strip())

    db.commit()
    db.refresh(admin_obj)

    log_info(f"Admin credentials updated by {current_admin.email} for role={payload.target_role}: new_email={admin_obj.email}")

    return {
        "success": True,
        "message": f"Credentials for {payload.target_role} updated successfully.",
        "admin": {
            "id": admin_obj.id,
            "name": admin_obj.name,
            "email": admin_obj.email,
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


