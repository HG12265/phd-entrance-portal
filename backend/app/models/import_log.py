from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base

class ImportLog(Base):
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, index=True)
    upload_type = Column(String(50), nullable=False)  # e.g., "candidate", "question"
    file_name = Column(String(255), nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    error_details = Column(Text, nullable=True)  # Store JSON as text
    uploaded_by = Column(Integer, nullable=True)  # Admin User ID
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
