import os
from dotenv import load_dotenv

# Load environmental configurations
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3307")
DB_NAME = os.getenv("DB_NAME", "phd_entrance_db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")

SECRET_KEY = os.getenv("SECRET_KEY", "9a6c764e528b368c7be8e1f0e2bfcd15d481b7e6d0a7fca5c52eb6b5c00e1234")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
CANDIDATE_TOKEN_EXPIRE_MINUTES = int(os.getenv("CANDIDATE_TOKEN_EXPIRE_MINUTES", "120"))

APP_ENV = os.getenv("APP_ENV", "development")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"
