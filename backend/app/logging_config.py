import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

# 1. Base log formatting
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 2. Main Logger config
main_logger = logging.getLogger("phd_app")
main_logger.setLevel(logging.INFO)

# Main App Handler (app.log)
app_handler = RotatingFileHandler("logs/app.log", maxBytes=10*1024*1024, backupCount=5)
app_handler.setFormatter(log_formatter)
app_handler.setLevel(logging.INFO)
main_logger.addHandler(app_handler)

# Error Handler (error.log)
error_handler = RotatingFileHandler("logs/error.log", maxBytes=10*1024*1024, backupCount=5)
error_handler.setFormatter(log_formatter)
error_handler.setLevel(logging.WARNING)
main_logger.addHandler(error_handler)

# 3. Exam Events Logger config
exam_logger = logging.getLogger("exam_events")
exam_logger.setLevel(logging.INFO)
exam_logger.propagate = False # Prevent writing candidate logs to main app.log

exam_handler = RotatingFileHandler("logs/exam_events.log", maxBytes=10*1024*1024, backupCount=5)
exam_handler.setFormatter(log_formatter)
exam_handler.setLevel(logging.INFO)
exam_logger.addHandler(exam_handler)

def log_info(message: str):
    main_logger.info(message)

def log_warning(message: str):
    main_logger.warning(message)

def log_error(message: str):
    main_logger.error(message)

def log_exam_event(event_type: str, candidate_id: Optional[int], attempt_id: Optional[int], status: str, details: str = ""):
    """
    Logs structured exam event details securely, omitting passwords, keys, or DOBs.
    """
    safe_msg = f"EVENT={event_type} | CANDIDATE_ID={candidate_id} | ATTEMPT_ID={attempt_id} | STATUS={status} | DETAILS={details}"
    exam_logger.info(safe_msg)
