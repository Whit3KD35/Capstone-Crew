from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.it_auth import create_it_token, get_current_it_user
from ...core.security import hashPassword, verifyPassword
from ...models import Clinician, Patient, Simulation, ITUser
from .patients import decrypt_patient

router = APIRouter(prefix="/it", tags=["it"])


# Auth 

class ITLoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
def it_login(data: ITLoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(ITUser).where(ITUser.email == data.email)).first()
    if not user or user.role != "it":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verifyPassword(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_it_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


# Clinician Management 

class CreateClinicianRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@router.get("/clinicians", dependencies=[Depends(get_current_it_user)])
def list_all_clinicians(session: Session = Depends(get_session)):
    clinicians = session.exec(select(Clinician)).all()
    return [{"id": str(c.id), "name": c.name, "email": c.email} for c in clinicians]

@router.post("/clinicians", dependencies=[Depends(get_current_it_user)])
def create_clinician(body: CreateClinicianRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(Clinician).where(Clinician.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")
    clinician = Clinician(name=body.name, email=body.email, password=hashPassword(body.password))
    session.add(clinician)
    session.commit()
    session.refresh(clinician)
    return {"id": str(clinician.id), "name": clinician.name, "email": clinician.email}

@router.delete("/clinicians/{clinician_id}", dependencies=[Depends(get_current_it_user)])
def delete_clinician(clinician_id: str, session: Session = Depends(get_session)):
    clinician = session.get(Clinician, clinician_id)
    if not clinician:
        raise HTTPException(status_code=404, detail="Clinician not found")
    session.delete(clinician)
    session.commit()
    return {"deleted": True, "id": clinician_id}


# Patient Overview 
@router.get("/patients", dependencies=[Depends(get_current_it_user)])
def list_all_patients(session: Session = Depends(get_session)):
    patients = session.exec(select(Patient)).all()
    return [decrypt_patient(session, p) for p in patients]


# Simulation Overview 

@router.get("/simulations", dependencies=[Depends(get_current_it_user)])
def list_all_simulations(session: Session = Depends(get_session)):
    sims = session.exec(select(Simulation)).all()
    return [
        {
            "id": str(s.id),
            "patient_id": str(s.patient_id),
            "medication_id": str(s.medication_id),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "flag_too_high": s.flag_too_high,
            "flag_too_low": s.flag_too_low,
        }
        for s in sims
    ]


# IT User Management

class CreateITUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@router.post("/users", dependencies=[Depends(get_current_it_user)])
def create_it_user(body: CreateITUserRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(ITUser).where(ITUser.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")
    user = ITUser(
        name=body.name,
        email=body.email,
        password=hashPassword(body.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"id": str(user.id), "name": user.name, "email": user.email, "role": user.role}
