from fastapi import APIRouter, Depends
from ...models import Patient, Medication
from sqlmodel import Session
from ...core.db import get_session

router = APIRouter(
    prefix="/patients",
    tags=["patients"]
)

@router.get("/")
def read_patient(session: Session = Depends(get_session)):
    return {"message": "read patient"}

@router.post("/")
def add_patient(patient: Patient, session: Session = Depends(get_session)):
    return {"message": "add patient with meds"}