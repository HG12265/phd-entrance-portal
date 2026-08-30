from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    exam_session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    submitted_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="in_progress", nullable=False)  # in_progress, submitted, auto_submitted, expired
    total_questions = Column(Integer, default=70, nullable=False)
    shuffled_question_order = Column(Text, nullable=False)  # Stores JSON string of question IDs
    
    # Phase 7 Fields
    score = Column(Integer, default=0, nullable=False)
    correct_count = Column(Integer, default=0, nullable=False)
    wrong_count = Column(Integer, default=0, nullable=False)
    unanswered_count = Column(Integer, default=0, nullable=False)
    result_status = Column(String(10), nullable=True)  # PASS, FAIL
    submission_type = Column(String(20), nullable=True)  # manual, auto
    # Phase 11 Fields
    active_lock_token = Column(String(191), nullable=True)
    lock_status = Column(String(50), default="unlocked", nullable=False)  # unlocked, locked, reopened
    locked_at = Column(DateTime, nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    reopened_by_admin_id = Column(Integer, nullable=True)
    reopen_reason = Column(Text, nullable=True)
    reopen_count = Column(Integer, default=0, nullable=False)
    last_client_fingerprint = Column(String(191), nullable=True)

    # Phase 14 Fields
    remaining_seconds_at_submit = Column(Integer, nullable=True)
    submitted_reopen_count = Column(Integer, default=0, nullable=False)
    submitted_reopened_at = Column(DateTime, nullable=True)
    submitted_reopened_by_admin_id = Column(Integer, nullable=True)
    submitted_reopen_reason = Column(Text, nullable=True)
    reopened_from_submitted = Column(Boolean, default=False, nullable=False)

    # Phase 17 Fields - Answer Snapshot Safety
    last_answer_snapshot_json = Column(Text, nullable=True)  # JSON snapshot of answers at submit time
    selected_count_at_submit = Column(Integer, nullable=True)  # Count of selected answers at submit

    # Phase 18 Fields - Reporting and Audit Enhancements
    login_time = Column(DateTime, nullable=True)
    system_ip = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    candidate = relationship("Candidate", back_populates="attempts")
    department = relationship("Department")
    exam_session = relationship("ExamSession")
    answers = relationship("CandidateAnswer", back_populates="attempt", cascade="all, delete-orphan")

