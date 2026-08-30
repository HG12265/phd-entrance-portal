from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db

router = APIRouter()

@router.get("/")
def list_exams(db: Session = Depends(get_db)):
  return {
    "message": "Exams router connected",
    "exams": [
      {"code": "CS-PHD-2026", "title": "Computer Science Entrance Exam"},
      {"code": "MA-PHD-2026", "title": "Mathematics Entrance Exam"}
    ]
  }
