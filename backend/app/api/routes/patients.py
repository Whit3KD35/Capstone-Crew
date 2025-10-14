from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlmodel import Session, select
from ...core.db import get_session
from ...models import Patient  # columns: id(uuid pk), name, number, email, age, weight, sex

router = APIRouter(prefix="/patients", tags=["patients"])

class PatientCreate(BaseModel):
    name: str
    number: str
    email: Optional[EmailStr] = None

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    number: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    weight: Optional[float] = None

@router.get("/")
def list_patients(session: Session = Depends(get_session)):
    return session.exec(select(Patient)).all()

@router.post("/")
def create_patient_basic(body: PatientCreate, session: Session = Depends(get_session)):
    p = Patient(name=body.name, number=body.number, email=body.email)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p

@router.get("/{email}")
def read_patient_by_email(email: str, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == email)).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

@router.post("/{email}")
def update_patient_by_email(email: str, body: PatientUpdate, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == email)).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(patient, k, v)

    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient
