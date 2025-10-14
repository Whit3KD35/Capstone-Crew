from fastapi import APIRouter, Depends, HTTPException
from ...models import Medication
from sqlmodel import Session, select
from ...core.db import get_session

router = APIRouter(
    prefix="/medications",
    tags=["medications"]
)

@router.get("/{}")
def get_medication_by_name(name: str, session: Session = Depends(get_session)):
    stmt = select(Medication).where(Medication.name == name)
    med = session.exec(stmt).first()

    if not med:
        raise HTTPException(status_code=404, message="Medication not found")
    return med