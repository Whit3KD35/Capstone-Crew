from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from datetime import datetime

from ...core.db import get_session
from ...core.patient_auth import create_patient_token
from ...core.security import decryptData, verifyPassword
from ...models import LoginRequest, Patient, User

router = APIRouter(prefix="/patient-login", tags=["patient-login"])


def _find_patient_by_email(session: Session, email: str) -> Patient | None:
    target = email.strip().lower()
    patients = session.exec(select(Patient)).all()
    for patient in patients:
        try:
            candidate = decryptData(patient.email).strip().lower()
        except Exception:
            candidate = str(patient.email).strip().lower()
        if candidate == target:
            return patient
    return None


def _find_user_by_email(session: Session, email: str) -> User | None:
    target = email.strip().lower()
    users = session.exec(select(User)).all()
    for user in users:
        raw = str(user.email).strip()
        if raw.lower() == target:
            return user
        try:
            dec = decryptData(raw)
        except Exception:
            dec = None
        if isinstance(dec, str) and dec.strip().lower() == target:
            return user
    return None


@router.post("/")
def patient_login(data: LoginRequest, session: Session = Depends(get_session)):
    user = _find_user_by_email(session, data.email)
    if not user or not verifyPassword(data.password, user.hashedPassword):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    patient = _find_patient_by_email(session, data.email)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()

    token = create_patient_token(patient.id)
    return {"access_token": token, "token_type": "bearer"}
