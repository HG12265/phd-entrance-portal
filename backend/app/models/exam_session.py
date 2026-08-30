from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

session_department_association = Table(
    "session_department_association",
    Base.metadata,
    Column("session_id", Integer, ForeignKey("exam_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("department_id", Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True)
)

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(191), nullable=False)
    exam_title = Column(String(191), default="PhD Entrance Examination", nullable=False)
    exam_date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=90, nullable=False)
    instructions = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    candidates = relationship("Candidate", back_populates="exam_session")
    departments = relationship("Department", secondary=session_department_association, back_populates="exam_sessions")

