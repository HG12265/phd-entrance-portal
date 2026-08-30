from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(191), unique=True, index=True, nullable=False)
    department_code = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    candidates = relationship("Candidate", back_populates="department")
    exams = relationship("Exam", back_populates="department")
    questions = relationship("Question", back_populates="department", cascade="all, delete-orphan")
    exam_sessions = relationship("ExamSession", secondary="session_department_association", back_populates="departments")

