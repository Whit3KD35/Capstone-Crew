from pydantic import BaseModel
from app.core.security import verifyPassword
from app.api.routes.users import getUserByEmail
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.db import get_session

router = APIRouter()

@router.post("/login")

class LoginRequest(BaseModel):
    email: str
    password: str

def authenticateUser(session: Session, email: str, password: str):
    user = getUserByEmail(session, email)

    if not user:
        return None

    if not verifyPassword(password, user.hashed_password):
        return None

    return user

def login(data: LoginRequest, session: Session = Depends(get_session)):
    user = authenticateUser(session, data.email, data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "message": "Login successful",
        "user_id": user.id
    }