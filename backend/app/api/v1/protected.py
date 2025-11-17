# app/api/v1/protected.py
from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/protected", tags=["protected"])

@router.get("/")
def protected_route(current_user: User = Depends(get_current_user)):
    return {"ok": True, "msg": "protected endpoint reached", "user": {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }}
