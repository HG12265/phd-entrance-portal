from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.admin import AdminUser
from app.utils.security import decode_access_token

# HTTPBearer security scheme to extract token from Authorization header
security_scheme = HTTPBearer()

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> AdminUser:
    """
    Dependency to fetch and validate the currently logged-in admin user.
    Expects a valid Bearer JWT token in the Authorization header.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if payload is None:
        raise credentials_exception
        
    email: str = payload.get("sub")
    admin_id: int = payload.get("admin_id")
    role: str = payload.get("role")
    
    if email is None or admin_id is None or role == "candidate":
        raise credentials_exception
        
    # Fetch admin from database
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id, AdminUser.email == email).first()
    
    if admin is None:
        raise credentials_exception
        
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive admin account"
        )
        
    return admin
