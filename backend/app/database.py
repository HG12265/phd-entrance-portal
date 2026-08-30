from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app import config

# Assemble connection string with PyMySQL and utf8mb4 encoding
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{config.DB_USER}:{config.DB_PASSWORD}@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}?charset=utf8mb4"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=100,
    max_overflow=100,
    pool_pre_ping=True  # Enables database connection health checks before queries
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# FastAPI dependency to provide scoped DB sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
