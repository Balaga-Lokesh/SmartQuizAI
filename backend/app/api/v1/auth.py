# app/api/v1/auth.py
"""
Auth endpoints for SmartQuiz AI:
- register, login, send-email-otp, verify-email-otp
- create_access_token and JWT helpers
- get_current_user dependency and /me endpoint
"""

from typing import Optional
from datetime import datetime, timedelta
import os
import secrets
import hashlib

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

import jwt  # PyJWT

from app.db.session import get_db
from app.models import EmailOTP, User
from app.core.security import hash_password as get_password_hash
from app.core.security import verify_password
from app.utils.email_sender import send_email_otp

router = APIRouter(prefix="/auth", tags=["auth"])

# Config (override via environment)
OTP_LENGTH = int(os.environ.get("EMAIL_OTP_LENGTH", 6))
OTP_TTL_SECONDS = int(os.environ.get("EMAIL_OTP_TTL_SECONDS", 300))  # 5 minutes
OTP_MAX_SENDS_PER_HOUR = int(os.environ.get("OTP_MAX_SENDS_PER_HOUR", 6))
OTP_HASH_SECRET = os.environ.get("OTP_HASH_SECRET", "dev-otp-secret-change-me")
DEV_SHOW_OTP = os.environ.get("DEV_SHOW_OTP", "0").lower() in ("1", "true", "yes")

SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")

# JWT settings
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-change-me")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# Security scheme for extraction
bearer_scheme = HTTPBearer(auto_error=False)

# --- Schemas ---
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[str] = "student"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SendOtpRequest(BaseModel):
    email: EmailStr
    purpose: Optional[str] = "login"

class VerifyEmailOtpRequest(BaseModel):
    email: EmailStr
    code: str
    purpose: Optional[str] = None  # "login" or "register" or None

# --- Helpers ---
def _now_utc() -> datetime:
    return datetime.utcnow()

def _generate_otp(length: int = OTP_LENGTH) -> str:
    return f"{secrets.randbelow(10 ** length):0{length}d}"

def _hash_with_salt(code: str, salt: str) -> str:
    h = hashlib.sha256()
    h.update(f"{code}{salt}{OTP_HASH_SECRET}".encode("utf-8"))
    return h.hexdigest()

def _throttle_exceeded(db: Session, email: str) -> bool:
    now = _now_utc()
    hour_ago = now - timedelta(hours=1)
    recent = db.query(EmailOTP).filter(
        EmailOTP.email == email,
        EmailOTP.created_at >= hour_ago
    ).count()
    return recent >= OTP_MAX_SENDS_PER_HOUR

def create_access_token(subject: str | int, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> dict:
    """
    Returns token dict: {"access_token": <str>, "token_type": "bearer", "expires_in": <seconds>}
    subject can be user id or email
    """
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)
    payload = {"sub": str(subject), "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": int(expires_minutes * 60)}

# --- JWT dependency / user loader ---
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency to get current user from Authorization: Bearer <token>.
    Raises 401 on missing/invalid token or if user not found.
    Returns SQLAlchemy User instance.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = int(sub)
    except Exception:
        # fallback: if subject is email, try lookup by email
        user = db.query(User).filter(User.email == sub).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found for token subject")
        return user

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# --- Endpoints ---
@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(req: RegisterRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if len(req.password) > 4096:
        raise HTTPException(status_code=400, detail="Password too long")

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(req.password)
    user = User(
        email=req.email,
        password_hash=hashed_pw,
        full_name=req.full_name,
        is_active=False,
        role=req.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if _throttle_exceeded(db, req.email):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    otp_plain = _generate_otp()
    salt = secrets.token_hex(8)
    hashed = _hash_with_salt(otp_plain, salt)
    expires_at = _now_utc() + timedelta(seconds=OTP_TTL_SECONDS)

    otp_row = EmailOTP(
        user_id=user.id,
        email=req.email,
        code=f"{hashed}|{salt}",
        expires_at=expires_at,
        used=False
    )
    db.add(otp_row)
    db.commit()

    try:
        background_tasks.add_task(send_email_otp, req.email, otp_plain, "Confirm your SmartQuiz account")
    except Exception as e:
        print("Failed to enqueue send_email_otp:", e)

    if (not SMTP_USER or not SMTP_PASS) or DEV_SHOW_OTP:
        print(f"[DEV] OTP for {req.email} = {otp_plain}")
        return {"detail": "user created, verification OTP sent (dev)", "otp": otp_plain}

    return {"detail": "user created, verification OTP sent"}

@router.post("/login", status_code=status.HTTP_200_OK)
def login_with_2fa(req: LoginRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Step 1 of login: verify credentials, then send OTP for 2FA.
    """
    user = db.query(User).filter(User.email == req.email).first()
    invalid_resp = HTTPException(status_code=401, detail="Invalid credentials")

    if not user:
        raise invalid_resp

    try:
        ok = verify_password(req.password, user.password_hash)
    except Exception as e:
        print("Password verify error:", e)
        raise HTTPException(status_code=500, detail="Password verification failed")

    if not ok:
        raise invalid_resp

    if _throttle_exceeded(db, req.email):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    otp_plain = _generate_otp()
    salt = secrets.token_hex(8)
    hashed = _hash_with_salt(otp_plain, salt)
    expires_at = _now_utc() + timedelta(seconds=OTP_TTL_SECONDS)

    otp_row = EmailOTP(
        user_id=user.id,
        email=req.email,
        code=f"{hashed}|{salt}",
        expires_at=expires_at,
        used=False
    )
    db.add(otp_row)
    db.commit()

    try:
        background_tasks.add_task(send_email_otp, req.email, otp_plain, "SmartQuiz login OTP")
    except Exception as e:
        print("Failed to enqueue send_email_otp:", e)

    if (not SMTP_USER or not SMTP_PASS) or DEV_SHOW_OTP:
        print(f"[DEV] Login OTP for {req.email} = {otp_plain}")
        return {"detail": "OTP sent (dev)", "otp": otp_plain}

    return {"detail": "OTP sent"}

@router.post("/send-email-otp", status_code=status.HTTP_200_OK)
def send_email_otp_endpoint(req: SendOtpRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if _throttle_exceeded(db, req.email):
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    otp_plain = _generate_otp()
    salt = secrets.token_hex(8)
    hashed = _hash_with_salt(otp_plain, salt)
    expires_at = _now_utc() + timedelta(seconds=OTP_TTL_SECONDS)

    otp_row = EmailOTP(
        user_id=None,
        email=req.email,
        code=f"{hashed}|{salt}",
        expires_at=expires_at,
        used=False
    )
    db.add(otp_row)
    db.commit()

    try:
        background_tasks.add_task(send_email_otp, req.email, otp_plain, "Your SmartQuiz OTP")
    except Exception as e:
        print("Failed to enqueue send_email_otp:", e)

    if (not SMTP_USER or not SMTP_PASS) or DEV_SHOW_OTP:
        print(f"[DEV] OTP for {req.email} = {otp_plain}")
        return {"detail": "OTP sent (dev)", "otp": otp_plain}

    return {"detail": "OTP sent"}

@router.post("/verify-email-otp", status_code=status.HTTP_200_OK)
def verify_email_otp_endpoint(req: VerifyEmailOtpRequest, db: Session = Depends(get_db)):
    """
    Verify OTP and optionally return JWT when purpose == "login".
    """
    now = _now_utc()

    otp_row = db.query(EmailOTP).filter(
        EmailOTP.email == req.email,
        EmailOTP.used == False,
        EmailOTP.expires_at >= now
    ).order_by(EmailOTP.created_at.desc()).first()

    if not otp_row:
        raise HTTPException(status_code=400, detail="No valid OTP found (maybe expired or not requested)")

    if "|" not in (otp_row.code or ""):
        raise HTTPException(status_code=500, detail="OTP stored in invalid format")

    stored_hash, salt = otp_row.code.split("|", 1)
    candidate_hash = _hash_with_salt(req.code, salt)

    if candidate_hash != stored_hash:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # mark used
    otp_row.used = True
    db.add(otp_row)

    token_payload: Optional[dict] = None

    # Activate associated user (if any)
    if otp_row.user_id:
        user = db.query(User).filter(User.id == otp_row.user_id).first()
        if user and not user.is_active:
            user.is_active = True
            db.add(user)

        # If verification purpose is login, issue a JWT for this user
        if req.purpose == "login":
            token_payload = create_access_token(subject=user.id)

    db.commit()

    if token_payload:
        return token_payload

    return {"detail": "verified"}

# --- New endpoint: /me ---
@router.get("/me", status_code=status.HTTP_200_OK)
def me_endpoint(current_user: User = Depends(get_current_user)):
    """
    Return basic info about the current user (from JWT).
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }
