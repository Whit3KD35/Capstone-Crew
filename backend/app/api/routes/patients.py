from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.patient_auth import get_current_patient
from ...models import Patient
from ...models import (
    Condition,
    Patient,
    PatientClinicalFactors,
    PatientConditionLink,
    PatientCurrentMedication,
    PatientVitalSigns,
)
from app.core.security import encryptData, decryptData


router = APIRouter(prefix="/patients", tags=["patients"])


def _decrypt_or_raw(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return decryptData(value)
    except Exception:
        return value


def _to_bool_or_none(v: Optional[str | bool]) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    val = v.strip().lower()
    if val in {"yes", "y", "true", "1"}:
        return True
    if val in {"no", "n", "false", "0"}:
        return False
    return None


def _find_patient_by_email(session: Session, email: str) -> Optional[Patient]:
    target = email.strip().lower()
    patients = session.exec(select(Patient)).all()
    for p in patients:
        try:
            candidate = _decrypt_or_raw(p.email).strip().lower()
            if candidate == target:
                return p
        except Exception:
            continue
    return None


def _get_factors(session: Session, patient_id) -> Optional[PatientClinicalFactors]:
    return session.exec(
        select(PatientClinicalFactors).where(PatientClinicalFactors.patient_id == patient_id)
    ).first()


def _get_vitals(session: Session, patient_id) -> Optional[PatientVitalSigns]:
    return session.exec(
        select(PatientVitalSigns).where(PatientVitalSigns.patient_id == patient_id)
    ).first()


def _get_conditions(session: Session, patient_id) -> list[str]:
    links = session.exec(
        select(PatientConditionLink).where(PatientConditionLink.patient_id == patient_id)
    ).all()
    names: list[str] = []
    for link in links:
        cond = session.get(Condition, link.condition_id)
        if cond:
            names.append(cond.name)
    return sorted(list(set(names)))


def _get_current_medications(session: Session, patient_id) -> list[str]:
    meds = session.exec(
        select(PatientCurrentMedication).where(PatientCurrentMedication.patient_id == patient_id)
    ).all()
    return sorted([m.name for m in meds if m.name])


def decrypt_patient(session: Session, p: Patient):
    factors = _get_factors(session, p.id)
    vitals = _get_vitals(session, p.id)
    conditions = _get_conditions(session, p.id)
    current_meds = _get_current_medications(session, p.id)
    return {
        "id": p.id,
        "name": _decrypt_or_raw(p.name),
        "email": _decrypt_or_raw(p.email),
        "phone": _decrypt_or_raw(p.phone) if p.phone else None,
        "full_name": _decrypt_or_raw(p.full_name) if p.full_name else None,
        "number": _decrypt_or_raw(p.number) if p.number else None,
        "age": p.age,
        "sex": p.sex,
        "weight_kg": p.weight_kg,
        "serum_creatinine_mg_dl": float(p.serum_creatinine_mg_dl) if p.serum_creatinine_mg_dl is not None else None,
        "creatinine_clearance_ml_min": float(p.creatinine_clearance_ml_min) if p.creatinine_clearance_ml_min is not None else None,
        "ckd_stage": _decrypt_or_raw(p.ckd_stage) if p.ckd_stage else None,
        "height_cm": float(factors.height_cm) if factors and factors.height_cm is not None else None,
        "is_pregnant": factors.is_pregnant if factors else None,
        "pregnancy_trimester": factors.pregnancy_trimester if factors else None,
        "is_breastfeeding": factors.is_breastfeeding if factors else None,
        "liver_disease_status": factors.liver_disease_status if factors else None,
        "albumin_g_dl": float(factors.albumin_g_dl) if factors and factors.albumin_g_dl is not None else None,
        "systolic_bp_mm_hg": vitals.systolic_bp_mm_hg if vitals else None,
        "diastolic_bp_mm_hg": vitals.diastolic_bp_mm_hg if vitals else None,
        "heart_rate_bpm": vitals.heart_rate_bpm if vitals else None,
        "conditions": conditions,
        "current_medications": current_meds,
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

    height_cm: Optional[float] = None
    is_pregnant: Optional[bool] = None
    pregnancy_trimester: Optional[str] = None
    is_breastfeeding: Optional[bool] = None
    liver_disease_status: Optional[str] = None
    albumin_g_dl: Optional[float] = None
    systolic_bp_mm_hg: Optional[int] = None
    diastolic_bp_mm_hg: Optional[int] = None
    heart_rate_bpm: Optional[int] = None
    conditions: Optional[list[str]] = None
    current_medications: Optional[list[str]] = None


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

    height_cm: Optional[float] = None
    is_pregnant: Optional[bool] = None
    pregnancy_trimester: Optional[str] = None
    is_breastfeeding: Optional[bool] = None
    liver_disease_status: Optional[str] = None
    albumin_g_dl: Optional[float] = None
    systolic_bp_mm_hg: Optional[int] = None
    diastolic_bp_mm_hg: Optional[int] = None
    heart_rate_bpm: Optional[int] = None
    conditions: Optional[list[str]] = None
    current_medications: Optional[list[str]] = None


def _upsert_factors_from_body(session: Session, patient_id, body_dict: dict) -> None:
    factor_keys = {
        "height_cm",
        "is_pregnant",
        "pregnancy_trimester",
        "is_breastfeeding",
        "liver_disease_status",
        "albumin_g_dl",
    }
    payload = {k: v for k, v in body_dict.items() if k in factor_keys}
    if not payload:
        return

    factors = _get_factors(session, patient_id)
    if not factors:
        factors = PatientClinicalFactors(patient_id=patient_id)

    if "is_pregnant" in payload:
        payload["is_pregnant"] = _to_bool_or_none(payload["is_pregnant"])
    if "is_breastfeeding" in payload:
        payload["is_breastfeeding"] = _to_bool_or_none(payload["is_breastfeeding"])

    for k, v in payload.items():
        setattr(factors, k, v)

    # Normalize dependent field
    if payload.get("is_pregnant") is False and "pregnancy_trimester" not in payload:
        factors.pregnancy_trimester = None

    session.add(factors)


def _upsert_vitals_from_body(session: Session, patient_id, body_dict: dict) -> None:
    vitals_keys = {"systolic_bp_mm_hg", "diastolic_bp_mm_hg", "heart_rate_bpm"}
    payload = {k: v for k, v in body_dict.items() if k in vitals_keys}
    if not payload:
        return
    vitals = _get_vitals(session, patient_id)
    if not vitals:
        vitals = PatientVitalSigns(patient_id=patient_id)
    for k, v in payload.items():
        setattr(vitals, k, v)
    session.add(vitals)


def _sync_conditions(session: Session, patient_id, conditions: Optional[list[str]]) -> None:
    if conditions is None:
        return
    existing_links = session.exec(
        select(PatientConditionLink).where(PatientConditionLink.patient_id == patient_id)
    ).all()
    for link in existing_links:
        session.delete(link)

    cleaned = sorted(list({c.strip() for c in conditions if c and c.strip()}))
    for name in cleaned:
        cond = session.exec(select(Condition).where(Condition.name == name)).first()
        if not cond:
            cond = Condition(name=name)
            session.add(cond)
            session.commit()
            session.refresh(cond)
        session.add(PatientConditionLink(patient_id=patient_id, condition_id=cond.id))


def _sync_current_medications(
    session: Session, patient_id, current_medications: Optional[list[str]]
) -> None:
    if current_medications is None:
        return
    existing = session.exec(
        select(PatientCurrentMedication).where(PatientCurrentMedication.patient_id == patient_id)
    ).all()
    for item in existing:
        session.delete(item)

    cleaned = sorted(list({m.strip() for m in current_medications if m and m.strip()}))
    for name in cleaned:
        session.add(PatientCurrentMedication(patient_id=patient_id, name=name))


@router.get("/")
def list_patients(session: Session = Depends(get_session)):
    patients = session.exec(select(Patient)).all()
    return [decrypt_patient(session, p) for p in patients]


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
        serum_creatinine_mg_dl=body.serum_creatinine_mg_dl,
        creatinine_clearance_ml_min=body.creatinine_clearance_ml_min,
        ckd_stage=encryptData(body.ckd_stage) if body.ckd_stage else None,
    )
    session.add(p)
    session.commit()
    session.refresh(p)

    body_dict = body.model_dump(exclude_none=True)
    _upsert_factors_from_body(session, p.id, body_dict)
    _upsert_vitals_from_body(session, p.id, body_dict)
    _sync_conditions(session, p.id, body.conditions)
    _sync_current_medications(session, p.id, body.current_medications)
    session.commit()

    return decrypt_patient(session, p)


@router.get("/{email}")
def read_patient_by_email(email: str, session: Session = Depends(get_session)):
    patient = _find_patient_by_email(session, email)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return decrypt_patient(session, patient)


@router.post("/{email}")
def update_patient_by_email(email: str, body: PatientUpdate, session: Session = Depends(get_session)):
    patient = _find_patient_by_email(session, email)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    payload = body.model_dump(exclude_none=True)
    relationship_keys = {"conditions", "current_medications"}

    # Encrypted fields
    if "name" in payload:
        patient.name = encryptData(str(payload.pop("name")))
    if "number" in payload:
        patient.number = encryptData(str(payload.pop("number")))
    if "phone" in payload:
        patient.phone = encryptData(str(payload.pop("phone")))
    if "full_name" in payload:
        patient.full_name = encryptData(str(payload.pop("full_name")))
    if "serum_creatinine_mg_dl" in payload:
        patient.serum_creatinine_mg_dl = payload.pop("serum_creatinine_mg_dl")
    if "creatinine_clearance_ml_min" in payload:
        patient.creatinine_clearance_ml_min = payload.pop("creatinine_clearance_ml_min")
    if "ckd_stage" in payload:
        patient.ckd_stage = encryptData(str(payload.pop("ckd_stage")))
    for rel_key in relationship_keys:
        payload.pop(rel_key, None)

    for k, v in payload.items():
        if hasattr(patient, k):
            setattr(patient, k, v)

    session.add(patient)
    _upsert_factors_from_body(session, patient.id, body.model_dump(exclude_none=True))
    _upsert_vitals_from_body(session, patient.id, body.model_dump(exclude_none=True))
    _sync_conditions(session, patient.id, body.conditions)
    _sync_current_medications(session, patient.id, body.current_medications)
    session.commit()
    session.refresh(patient)
    return patient

@router.get("/me")
def get_my_profile(
    session: Session = Depends(get_session),
    user: dict = Depends(get_current_patient),
):
    patient = session.get(Patient, user["patient_id"])
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.post("/me")
def update_my_profile(
    body: PatientUpdate,
    session: Session = Depends(get_session),
    user: dict = Depends(get_current_patient),
):
    patient = session.get(Patient, user["patient_id"])
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(patient, k, v)

    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient
    return decrypt_patient(session, patient)
