from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.candidate import Candidate
from app.utils.security import decode_access_token

# HTTPBearer security scheme to extract token from Authorization header
security_scheme = HTTPBearer()

def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Candidate:
    """
    Dependency to fetch and validate the currently logged-in candidate.
    Expects a valid Bearer JWT token in the Authorization header.
    Rejects any tokens that do not have the 'candidate' role.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate candidate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if payload is None:
        raise credentials_exception
        
    app_num: str = payload.get("sub")
    candidate_id: int = payload.get("candidate_id")
    role: str = payload.get("role")
    
    if app_num is None or candidate_id is None or role != "candidate":
        raise credentials_exception
        
    # Fetch candidate from database
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id, Candidate.application_number == app_num).first()
    
    if candidate is None:
        raise credentials_exception
        
    if not candidate.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive candidate account"
        )
        
    return candidate
