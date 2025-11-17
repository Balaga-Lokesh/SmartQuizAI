# backend/app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Create SQLAlchemy engine from DATABASE_URL
engine = create_engine(settings.DATABASE_URL, echo=False, future=True)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Base for models
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
