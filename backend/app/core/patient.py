from fastapi import Depends
from app.core.security import encryptData
from app.models import Patient
from sqlmodel import Session
from app.core.security import decryptData
from app.core.db import get_session
from fastapi import APIRouter

router = APIRouter()

def createPatient(session: Session, notes: str):
    encrypted = encryptData(notes)

    patient = Patient(encryptedNotes=encrypted)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient

def getPatient(session: Session, patient_id: int):
    patient = session.get(Patient, patient_id)

    decryptedNotes = decryptData(patient.encryptedNotes)

    return {
        "id": patient.id,
        "notes": decryptedNotes
    }

@router.get("/patients/{patient_id}")
def read_patient(patient_id: int, session: Session = Depends(get_session)):
    return getPatient(session, patient_id)
