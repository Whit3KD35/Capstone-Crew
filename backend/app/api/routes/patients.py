from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import EmailStr
from ...models import Patient, Medication
from sqlmodel import Session
from ...core.db import get_session

router = APIRouter(
    prefix="/patients",
    tags=["patients"]
)

@router.post("/")
def create_patient_basic(patient: Patient, session: Session = Depends(get_session)):
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient

@router.post("/{email}")
def update_patient_body(email: EmailStr, body_info: Patient = Body(...), session: Session = Depends(get_session)):
    patient = session.get(Patient, email)
    if not patient:
        raise HTTPException(status_code=404, message="No patient found")
    
    for field, value in body_info.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    session.commit()
    session.refresh(patient)
    return patient
    

@router.get("/")
def read_all_patient(session: Session = Depends(get_session)):
    return {"message": "temp to read all patients"}

@router.get("/{email}")
def read_patient_by_email(email: EmailStr, session: Session = Depends(get_session)):
    patient = session.get(Patient, email)
    if not patient:
        raise HTTPException(status_code=404, message="Patient not found")
    return patient