from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError

SECRET_KEY = "CHANGE_ME"  # move to .env later
ALGORITHM = "HS256"
EXPIRE_MINUTES = 60

patient_oauth2 = OAuth2PasswordBearer(tokenUrl="/patient-login/")

def create_patient_token(patient_id: int) -> str:
    payload = {
        "role": "patient",
        "patient_id": patient_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_patient(token: str = Depends(patient_oauth2)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "patient" or payload.get("patient_id") is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Patient access only",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
