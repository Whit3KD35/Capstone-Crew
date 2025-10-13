from fastapi import APIRouter, Depends
from ...models import Medication
from sqlmodel import Session
from ...core.db import get_session

router = APIRouter(
    prefix="/sims",
    tags=["sims"]
)

@router.get("/{}")
def get_medication_by_name(session: Session = Depends(get_session)):
    return {"message": "add sim"}