from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional, List
from app.schemas.department_schema import DepartmentResponse

class ExamSessionCreate(BaseModel):
    session_name: str
    exam_title: Optional[str] = "PhD Entrance Examination"
    exam_date: date
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    instructions: Optional[str] = None
    department_ids: Optional[List[int]] = []

    @field_validator("start_time")
    @classmethod
    def check_times(cls, start_time: datetime, info) -> datetime:
        # Pydantic v2 style validation
        # The end_time will be validated after start_time, so we do validation in a custom route instead
        # or we check duration_minutes is positive here.
        if start_time is None:
            raise ValueError("start_time is required")
        return start_time

class ExamSessionUpdate(BaseModel):
    session_name: Optional[str] = None
    exam_title: Optional[str] = None
    exam_date: Optional[date] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None
    department_ids: Optional[List[int]] = None

class ExamSessionResponse(BaseModel):
    id: int
    session_name: str
    exam_title: str
    exam_date: date
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    instructions: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    departments: List[DepartmentResponse] = []

    class Config:
        from_attributes = True

