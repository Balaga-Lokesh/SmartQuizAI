# backend/app/crud.py
from sqlalchemy.orm import Session
from app import models, schemas
from app.core import security
from datetime import datetime, timedelta
import random
from typing import Optional

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate, role: str = "teacher"):
    hashed = security.hash_password(user.password)
    db_user = models.User(email=user.email, full_name=user.full_name, password_hash=hashed, role=role)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_quiz(db: Session, creator_id: int, quiz_in: schemas.QuizCreate):
    db_quiz = models.Quiz(
        creator_id=creator_id,
        title=quiz_in.title,
        topic=quiz_in.topic,
        description=quiz_in.description,
        difficulty=quiz_in.difficulty,
    )
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

# OTP helpers
def create_email_otp(db: Session, email: str, user_id: Optional[int] = None, ttl_seconds: int = 300):
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    otp = models.EmailOTP(user_id=user_id, email=email, code=code, expires_at=expires_at)
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp

def get_valid_otp(db: Session, email: str, code: str):
    now = datetime.utcnow()
    return (
        db.query(models.EmailOTP)
        .filter(models.EmailOTP.email == email, models.EmailOTP.code == code, models.EmailOTP.used == False, models.EmailOTP.expires_at >= now)
        .order_by(models.EmailOTP.created_at.desc())
        .first()
    )

def mark_otp_used(db: Session, otp: models.EmailOTP):
    otp.used = True
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp
