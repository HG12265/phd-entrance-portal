import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db, engine
from app.config import APP_ENV, ENABLE_DOCS, CORS_ORIGINS
from app.logging_config import log_error, log_info
from app.routes import (
    admin_routes, candidate_routes, department_routes, question_routes, 
    exam_routes, admin_report_routes, candidate_auth_routes, 
    exam_session_routes, candidate_exam_routes, candidate_attempt_routes, 
    candidate_submit_routes, admin_exam_control_routes, settings_routes
)

# Ensure uploads directories exist before server startup to prevent StaticFiles mount errors
os.makedirs(os.path.join("uploads", "candidate_photos"), exist_ok=True)
os.makedirs(os.path.join("uploads", "candidate_excels"), exist_ok=True)
os.makedirs(os.path.join("uploads", "question_excels"), exist_ok=True)
os.makedirs(os.path.join("uploads", "question_images"), exist_ok=True)

# Configure Swagger/OpenAPI docs based on APP_ENV and ENABLE_DOCS
docs_url = "/docs"
redoc_url = "/redoc"
openapi_url = "/openapi.json"

if APP_ENV == "production" and not ENABLE_DOCS:
    docs_url = None
    redoc_url = None
    openapi_url = None

app = FastAPI(
    title="PhD Entrance Exam Portal API",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url
)

# Configure CORS middleware
origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_error(f"Unhandled error occurred: path={request.url.path} error={str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please contact administrator."}
    )

# Request logging middleware (excluding sensitive payloads or credentials)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Secure logging: log request details safely (never passwords, DOB, or JWTs)
    log_info(f"Request: method={request.method} path={request.url.path} status={response.status_code} duration={duration:.4f}s")
    return response

# Static file serving for candidate photographs
app.mount(
    "/static/candidate_photos",
    StaticFiles(directory=os.path.join("uploads", "candidate_photos")),
    name="candidate_photos"
)

# Static file serving for question images
app.mount(
    "/static/question_images",
    StaticFiles(directory=os.path.join("uploads", "question_images")),
    name="question_images"
)

# Root Test Route
@app.get("/")
def read_root():
    return {"message": "PhD Entrance Exam Portal API Running Successfully"}

# Health Check Route
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db_connected = False
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        # Do not expose stack traces or DB host details
        log_error(f"Health check database ping failed: {str(e)}")
        
    return {
        "status": "OK" if db_connected else "ERROR",
        "database": "connected" if db_connected else "disconnected",
        "timestamp": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    }

# Include Routers with Phase 3 and Phase 5 prefixes
app.include_router(admin_routes.router, prefix="/api/admin/auth", tags=["Admin Authentication"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin System Management"])
app.include_router(department_routes.router, prefix="/api/admin/departments", tags=["Department Management"])
app.include_router(candidate_routes.router, prefix="/api/admin/candidates", tags=["Candidate Management"])
app.include_router(question_routes.router, prefix="/api/admin/questions", tags=["Question Management"])
app.include_router(exam_session_routes.router, prefix="/api/admin/exam-sessions", tags=["Admin Exam Sessions"])
app.include_router(admin_report_routes.router, tags=["Admin Reports"])
app.include_router(admin_exam_control_routes.router)

# Candidate routes
app.include_router(candidate_auth_routes.router, prefix="/api/candidate/auth", tags=["Candidate Authentication"])
app.include_router(candidate_exam_routes.router, prefix="/api/candidate", tags=["Candidate Exam System"])
app.include_router(candidate_attempt_routes.router, prefix="/api/candidate/exam", tags=["Candidate Exam Attempt"])
app.include_router(candidate_submit_routes.router, tags=["Candidate Exam Submit"])

# Keep other endpoints accessible
app.include_router(exam_routes.router, prefix="/api/exam", tags=["Exam"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["System Settings"])
