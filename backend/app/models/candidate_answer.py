from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    selected_option = Column(String(10), nullable=True)  # A, B, C, D, or null
    answer_status = Column(String(50), default="not_visited", nullable=False)  # not_visited, not_answered, answered, marked_for_review, answered_marked_for_review
    answered_at = Column(DateTime, nullable=True)
    
    # Phase 7 Fields
    is_correct = Column(Boolean, nullable=True)
    mark_awarded = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
    )

    # Relationships
    attempt = relationship("ExamAttempt", back_populates="answers")
    question = relationship("Question")
