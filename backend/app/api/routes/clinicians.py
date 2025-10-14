from fastapi import APIRouter, Depends
from ...models import Clinician
from sqlmodel import Session
from ...core.db import get_session

router = APIRouter(
    prefix="/clinicians",
    tags=["clinicians"]
)

'''
@router.get("/")
def read_clinician(session: Session = Depends(get_session)):
    return {"message": "read clinician"}

@router.post("/")
def add_clinican(clinician: Clinician, session: Session = Depends(get_session)):
    return {"message": "add clinician"}
'''