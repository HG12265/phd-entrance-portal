from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import datetime

class Exam(Base):
  __tablename__ = "exams"

  id = Column(Integer, primary_key=True, index=True)
  title = Column(String(191), nullable=False)
  exam_code = Column(String(50), unique=True, index=True, nullable=False)
  duration_minutes = Column(Integer, default=120)
  total_questions = Column(Integer, default=100)
  department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)

  # Relationships
  department = relationship("Department", back_populates="exams")
