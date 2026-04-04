from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select, Session
from ...core.db import get_session
from ...models import Clinician, LoginRequest
from datetime import datetime
from ...core.security import hashPassword, verifyPassword

router = APIRouter(
    prefix="/login",
    tags=["login"]
)

@router.post("/")
def clinician_login(data: LoginRequest, session: Session = Depends(get_session)):
    stmt = select(Clinician).where(Clinician.email == data.email)
    clinician = session.exec(stmt).first()

    if not clinician:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    is_valid_password = verifyPassword(data.password, clinician.password)

    if not is_valid_password and clinician.password == data.password:
        clinician.password = hashPassword(data.password)
        is_valid_password = True

    if not is_valid_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    clinician.last_login = datetime.utcnow()
    session.add(clinician)
    session.commit()

    return {
        "message": "Login successful",
        "clinician_id": clinician.id
    }
