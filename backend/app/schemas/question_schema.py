from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class QuestionResponse(BaseModel):
    id: int
    department_id: int
    department_name: Optional[str] = None
    question_no: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    marks: int
    is_active: bool
    image_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class QuestionAdminPreviewResponse(BaseModel):
    id: int
    department_id: int
    department_name: Optional[str] = None
    question_no: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    marks: int
    is_active: bool
    image_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class QuestionCandidateViewResponse(BaseModel):
    id: int
    department_id: int
    question_no: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    marks: int
    image_path: Optional[str] = None

    class Config:
        from_attributes = True

class QuestionUploadErrorDetail(BaseModel):
    row: int
    question_no: Optional[int] = None
    error: str

class QuestionUploadSummary(BaseModel):
    message: str
    department_id: int
    department_name: str
    total_rows: int
    success_count: int
    failed_count: int
    replaced_existing: bool
    errors: List[QuestionUploadErrorDetail]

class QuestionListResponse(BaseModel):
    items: List[QuestionResponse]
    total: int
    page: int
    limit: int
    pages: int

class DepartmentQuestionSummary(BaseModel):
    department_id: int
    department_name: str
    active_questions: int
    inactive_questions: int
    is_ready: bool
    last_uploaded_at: Optional[datetime] = None
    last_import_batch_id: Optional[str] = None

class DashboardQuestionSummary(BaseModel):
    total_departments: int
    ready_departments: int
    pending_departments: int
    total_active_questions: int
