from fastapi import APIRouter, HTTPException, Depends, Path
from pydantic import BaseModel, EmailStr
from typing import Any, Optional
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from ...core.db import get_session
from ...models import Clinician

router = APIRouter(prefix="/clinicians", tags=["clinicians"])

class ClinicianCreate(BaseModel):

    email: EmailStr
    password: str

    first_name: Optional[str] = None
    last_name: Optional[str]  = None
    name: Optional[str]       = None

def as_public_dict(row: Clinician) -> dict[str, Any]:
    """Serialize a Clinician without sensitive fields, regardless of column names."""
    data = row.model_dump(exclude_none=True)
    for k in ["password", "password_hash", "hashed_password"]:
        data.pop(k, None)
    return data

def build_clinician_kwargs(body: ClinicianCreate) -> dict[str, Any]:
    """Only pass fields that actually exist on the Clinician model."""
    body_dict = body.model_dump(exclude_none=True)
    model_fields = getattr(Clinician, "model_fields", {})
    kwargs = {}

    for k, v in body_dict.items():
        if k in model_fields:
            kwargs[k] = v

    if "name" in body_dict and "first_name" in model_fields and "last_name" in model_fields:
        parts = body_dict["name"].strip().split()
        if parts:
            kwargs["first_name"] = parts[0]
            if len(parts) > 1:
                kwargs["last_name"] = " ".join(parts[1:])

    return kwargs

# Routes
@router.get("/")
def list_clinicians(session: Session = Depends(get_session)):
    rows = session.exec(select(Clinician)).all()
    return [as_public_dict(r) for r in rows]

@router.post("/")
def create_clinician(body: ClinicianCreate, session: Session = Depends(get_session)):
    if "email" in getattr(Clinician, "model_fields", {}):
        existing = session.exec(select(Clinician).where(Clinician.email == body.email)).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already exists")

    kwargs = build_clinician_kwargs(body)
    if not kwargs:
        raise HTTPException(status_code=400, detail="No valid fields for Clinician")

    clinician = Clinician(**kwargs)
    session.add(clinician)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    session.refresh(clinician)
    return as_public_dict(clinician)
