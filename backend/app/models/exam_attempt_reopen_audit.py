from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class ExamAttemptReopenAudit(Base):
    __tablename__ = "exam_attempt_reopen_audits"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    reopen_type = Column(String(50), nullable=False)  # device_unlock, submitted_force_reopen
    old_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    old_end_time = Column(DateTime, nullable=True)
    new_end_time = Column(DateTime, nullable=True)
    remaining_seconds_granted = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    
    # Safeguard fields
    old_submitted_time = Column(DateTime, nullable=True)
    old_score = Column(Integer, nullable=True)
    old_result_status = Column(String(50), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
