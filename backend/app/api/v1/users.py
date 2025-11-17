# app/api/v1/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app import models

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[dict])
def list_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    # minimal serialization
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active, "role": u.role} for u in users]
