from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlmodel import Session, select
from ...core.db import get_session
from ...models import Patient
from app.core.security import encryptData, decryptData

router = APIRouter(prefix="/patients", tags=["patients"])

def decrypt_patient(p: Patient):
    return {
        "id": p.id,
        "name": decryptData(p.name),
        "email": decryptData(p.email),
        "phone": decryptData(p.phone) if p.phone else None,
        "full_name": decryptData(p.full_name) if p.full_name else None,
        "number": decryptData(p.number) if p.number else None,
        "age": p.age,
        "sex": p.sex,
        "weight_kg": p.weight_kg,
        "serum_creatinine_mg_dl": p.serum_creatinine_mg_dl if p.serum_creatinine_mg_dl else None,
        "creatinine_clearance_ml_min": p.creatinine_clearance_ml_min if p.creatinine_clearance_ml_min else None,
        "ckd_stage": decryptData(p.ckd_stage) if p.ckd_stage else None
    }

class PatientCreate(BaseModel):
    name: str
    email: EmailStr
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

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    number: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    weight: Optional[int] = None
    serum_creatinine_mg_dl: Optional[float] = None
    creatinine_clearance_ml_min: Optional[float] = None
    ckd_stage: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    weight_kg: Optional[float] = None

@router.get("/")
def list_patients(session: Session = Depends(get_session)):
    patients = session.exec(select(Patient)).all()
    return [decrypt_patient(p) for p in patients]

@router.post("/")
def create_patient_basic(body: PatientCreate, session: Session = Depends(get_session)):
    p = Patient(
    name=encryptData(body.name),
    email=encryptData(body.email),
    phone=encryptData(body.phone) if body.phone else None,
    full_name=encryptData(body.full_name) if body.full_name else None,
    number=encryptData(body.number) if body.number else None,
    age=body.age,
    sex=body.sex,
    weight_kg=body.weight_kg,
    serum_creatinine_mg_dl=body.serum_creatinine_mg_dl if body.serum_creatinine_mg_dl else None,
    creatinine_clearance_ml_min=body.creatinine_clearance_ml_min if body.creatinine_clearance_ml_min else None,
    ckd_stage=encryptData(body.ckd_stage) if body.ckd_stage else None
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p

@router.get("/{email}")
def read_patient_by_email(email: str, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == encryptData(email))).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return decrypt_patient(patient)

@router.post("/{email}")
def update_patient_by_email(email: str, body: PatientUpdate, session: Session = Depends(get_session)):
    patient = session.exec(select(Patient).where(Patient.email == encryptData(email))).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(patient, k, v)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return decrypt_patient(patient)
