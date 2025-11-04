from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from ...core.db import get_session
from ...models import Medication

router = APIRouter(prefix="/medications", tags=["medications"])


class MedicationCreate(BaseModel):
    name: str
    generic_name: Optional[str] = None
    half_life_hr: Optional[float] = None
    clearance_l_hr: Optional[float] = None
    volume_of_distribution_l: Optional[float] = None
    bioavailability_f: Optional[float] = None
    therapeutic_window_lower_mg_l: Optional[float] = None
    therapeutic_window_upper_mg_l: Optional[float] = None
    source_url: Optional[HttpUrl] = None


class MedicationUpdate(BaseModel):
    generic_name: Optional[str] = None
    half_life_hr: Optional[float] = None
    clearance_l_hr: Optional[float] = None
    volume_of_distribution_l: Optional[float] = None
    bioavailability_f: Optional[float] = None
    therapeutic_window_lower_mg_l: Optional[float] = None
    therapeutic_window_upper_mg_l: Optional[float] = None
    source_url: Optional[HttpUrl] = None


@router.get("/")
def list_medications(session: Session = Depends(get_session)):
    return session.exec(select(Medication)).all()


@router.get("/{name}")
def get_medication_by_name(name: str, session: Session = Depends(get_session)):
    med = session.exec(select(Medication).where(Medication.name == name)).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    return med


@router.post("/")
def create_medication(body: MedicationCreate, session: Session = Depends(get_session)):
    data = body.model_dump(exclude_none=True)
    if "source_url" in data and data["source_url"] is not None:
        data["source_url"] = str(data["source_url"])
    med = Medication(**data)
    session.add(med)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(select(Medication).where(Medication.name == body.name)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Medication already exists")
        raise
    session.refresh(med)
    return med


@router.post("/{name}")
def update_medication(name: str, body: MedicationUpdate, session: Session = Depends(get_session)):
    med = session.exec(select(Medication).where(Medication.name == name)).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    updates = body.model_dump(exclude_none=True)
    if "source_url" in updates and updates["source_url"] is not None:
        updates["source_url"] = str(updates["source_url"])

    for key, value in updates.items():
        setattr(med, key, value)

    session.add(med)
    session.commit()
    session.refresh(med)
    return med
