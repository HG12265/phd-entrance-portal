from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    application_number = Column(String(191), unique=True, index=True, nullable=False)
    name = Column(String(191), nullable=False)
    email = Column(String(191), nullable=True)
    dob = Column(Date, nullable=False)
    mobile_number = Column(String(50), nullable=True)
    applied_subject = Column(String(191), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    photo_filename = Column(String(255), nullable=True)
    photo_path = Column(String(255), nullable=True)
    photo_status = Column(String(50), default="missing", nullable=False)
    
    # Phase 12 new columns
    application_id = Column(String(191), unique=True, index=True, nullable=True)
    applicant_name = Column(String(191), nullable=True)
    initial = Column(String(50), nullable=True)
    category_ft_pt = Column(String(50), nullable=True)
    programme_offered = Column(String(191), nullable=True)
    subject = Column(String(191), nullable=True)
    original_department_text = Column(String(191), nullable=True)

    import_batch_id = Column(String(191), nullable=True)
    exam_session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    department = relationship("Department", back_populates="candidates")
    attempts = relationship("ExamAttempt", back_populates="candidate")
    exam_session = relationship("ExamSession", back_populates="candidates")
