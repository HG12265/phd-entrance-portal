from pydantic import BaseModel
from typing import Optional

class CandidateLoginRequest(BaseModel):
    application_number: str
    dob: str

class CandidateAuthResponse(BaseModel):
    id: int
    application_number: str
    name: str
    applied_subject: str
    department_id: int
    department_name: str

    class Config:
        from_attributes = True

class CandidateLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    candidate: CandidateAuthResponse

class CandidateProfileResponse(BaseModel):
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
    dob: str  # Format returned will be YYYY-MM-DD or formatted string
    mobile_number: Optional[str] = None
    applied_subject: str
    department_id: int
    department_name: str
    photo_status: str
    photo_url: Optional[str] = None

    class Config:
        from_attributes = True
