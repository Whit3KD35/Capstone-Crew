# app/api/routes/patient_login.py
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from ...core.db import get_session
from ...models import Patient, LoginRequest
from ...core.patient_auth import create_patient_token

router = APIRouter(
    prefix="/patient-login",
    tags=["patient-login"],
)

@router.post("/")
def patient_login(data: LoginRequest, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == data.email)).first()

    # NOTE: this requires Patient.password to exist in your model/table
    if not patient or patient.password != data.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_patient_token(patient.id)
    return {"access_token": token, "token_type": "bearer"}
"""
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.patient_auth import get_current_patient
# from ...core.patient_auth import create_patient_token
from ...models import Patient, LoginRequest

router = APIRouter(prefix="/patients", tags=["patients"])

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    number: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    sex: Optional[str] = None
    serum_creatinine_mg_dl: Optional[float] = None
    creatinine_clearance_ml_min: Optional[float] = None
    ckd_stage: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    weight_kg: Optional[float] = None

@router.post("/")
def patient_login(data: LoginRequest, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == data.email)).first()

    # NOTE: this requires Patient.password to exist in your model/table
    if not patient or patient.password != data.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_patient_token(patient.id)
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def get_my_profile(
    session: Session = Depends(get_session),
    user: dict = Depends(get_current_patient),
):
    patient_id = user["patient_id"]
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@router.post("/me")
def update_my_profile(
    body: PatientUpdate,
    session: Session = Depends(get_session),
    user: dict = Depends(get_current_patient),
):
    patient_id = user["patient_id"]
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(patient, k, v)

    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient
"""
# app/api/routes/patient_login.py
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.patient_auth import create_patient_token
from ...models import Patient, LoginRequest

router = APIRouter(prefix="/patient-login", tags=["patient-login"])

@router.post("/")
def patient_login(data: LoginRequest, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == data.email)).first()

    if not patient or patient.password != data.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_patient_token(patient.id)
    return {"access_token": token, "token_type": "bearer"}
