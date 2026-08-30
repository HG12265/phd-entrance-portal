from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DepartmentBase(BaseModel):
    department_name: str = Field(..., min_length=1)
    department_code: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_active: Optional[bool] = True

class DepartmentCreate(BaseModel):
    department_name: str = Field(..., min_length=1, description="Name of the department")
    department_code: str = Field(..., min_length=1, description="Unique short code of the department")
    description: Optional[str] = None

class DepartmentUpdate(BaseModel):
    department_name: Optional[str] = None
    department_code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class DepartmentResponse(BaseModel):
    id: int
    department_name: str
    department_code: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
