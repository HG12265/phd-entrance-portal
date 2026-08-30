from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import date, datetime

class CandidateResponse(BaseModel):
    id: int
    application_number: str
    application_id: Optional[str] = None
    applicant_name: Optional[str] = None
    initial: Optional[str] = None
    category_ft_pt: Optional[str] = None
    programme_offered: Optional[str] = None
    subject: Optional[str] = None
    original_department_text: Optional[str] = None
    name: str
    email: Optional[str] = None
    dob: date
    mobile_number: Optional[str] = None
    applied_subject: str
    department_id: int
    department_name: Optional[str] = None
    photo_filename: Optional[str] = None
    photo_path: Optional[str] = None
    photo_status: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class CandidateListResponse(BaseModel):
    items: List[CandidateResponse]
    total: int
    page: int
    limit: int
    pages: int

class UploadErrorDetail(BaseModel):
    row: int
    application_id: Optional[str] = None
    error: str

class CandidateUploadSummary(BaseModel):
    message: str
    total_rows: int
    success_count: int
    failed_count: int
    photo_available_count: int
    photo_missing_count: int
    duplicate_in_excel_count: int
    duplicate_in_database_count: int
    errors: List[UploadErrorDetail]

class CandidateManualCreate(BaseModel):
    # Old fields for backward compatibility
    name: Optional[str] = None
    application_number: Optional[str] = None
    applied_subject: Optional[str] = None
    
    # Phase 12 new fields
    application_id: Optional[str] = None
    applicant_name: Optional[str] = None
    initial: Optional[str] = None
    category_ft_pt: Optional[str] = None
    programme_offered: Optional[str] = None
    subject: Optional[str] = None
    original_department_text: Optional[str] = None
    
    # Shared fields
    email: Optional[str] = None
    dob: str
    mobile_number: Optional[str] = None
    exam_session_id: Optional[int] = None
