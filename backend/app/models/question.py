from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), index=True, nullable=False)
    question_no = Column(Integer, nullable=False)
    
    # Text/LONGTEXT compatible fields supporting Unicode (utf8mb4)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    
    correct_option = Column(String(10), nullable=False) # A/B/C/D
    marks = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    import_batch_id = Column(String(100), nullable=True)
    image_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    department = relationship("Department", back_populates="questions")
    answers = relationship("CandidateAnswer", back_populates="question")

