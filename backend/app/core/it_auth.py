import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("FERNET_KEY") or "CHANGE_ME"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 60

it_oauth2 = OAuth2PasswordBearer(tokenUrl="/it/login")

def create_it_token(user_id: Any) -> str:
    payload = {
        "role": "it",
        "user_id": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_it_user(token: str = Depends(it_oauth2)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "it" or payload.get("user_id") is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IT access only",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
