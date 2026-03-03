from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
from sqlmodel import Session, select
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from ...core.db import get_session
from ...models import (
    Medication,
    MedicationTherapeuticWindowReview,
    PatientMedicationLink,
    Simulation,
)
from ...pharmacokinetics import (
    _float_to_dec,
    _dec_to_float,
)

router = APIRouter(prefix="/medications", tags=["medications"])


class MedicationCreate(BaseModel):
    name: str
    generic_name: Optional[str] = None
    half_life_hr: Optional[float] = None
    clearance_raw_value: Optional[float] = None
    clearance_raw_unit: Optional[str] = None
    volume_of_distribution_raw_value: Optional[float] = None
    volume_of_distribution_raw_unit: Optional[str] = None
    bioavailability_f: Optional[float] = None
    therapeutic_window_lower_mg_l: Optional[float] = None
    therapeutic_window_upper_mg_l: Optional[float] = None
    source_url: Optional[HttpUrl] = None


class MedicationUpdate(BaseModel):
    generic_name: Optional[str] = None
    half_life_hr: Optional[float] = None
    clearance_raw_value: Optional[float] = None
    clearance_raw_unit: Optional[str] = None
    volume_of_distribution_raw_value: Optional[float] = None
    volume_of_distribution_raw_unit: Optional[str] = None
    bioavailability_f: Optional[float] = None
    therapeutic_window_lower_mg_l: Optional[float] = None
    therapeutic_window_upper_mg_l: Optional[float] = None
    source_url: Optional[HttpUrl] = None


_DECIMAL_FIELDS = {
    "half_life_hr",
    "clearance_raw_value",
    "volume_of_distribution_raw_value",
    "bioavailability_f",
    "therapeutic_window_lower_mg_l",
    "therapeutic_window_upper_mg_l",
}


def _normalize_medication_payload(data: dict) -> dict:
    out = dict(data)
    if "source_url" in out and out["source_url"] is not None:
        out["source_url"] = str(out["source_url"])
    for k in _DECIMAL_FIELDS:
        if k in out and out[k] is not None:
            out[k] = _float_to_dec(float(out[k]))
    return out


class WindowReviewResponse(BaseModel):
    medication_id: str
    status: str
    lower_mg_l: Optional[float] = None
    upper_mg_l: Optional[float] = None
    source: Optional[str] = None
    confidence_pct: Optional[float] = None
    reviewer_notes: Optional[str] = None
    updated_at: Optional[str] = None


class WindowRejectRequest(BaseModel):
    notes: Optional[str] = None
    manual_lower_mg_l: Optional[float] = None
    manual_upper_mg_l: Optional[float] = None


def _to_review_response(row: MedicationTherapeuticWindowReview) -> WindowReviewResponse:
    return WindowReviewResponse(
        medication_id=str(row.medication_id),
        status=row.status,
        lower_mg_l=_dec_to_float(row.lower_mg_l),
        upper_mg_l=_dec_to_float(row.upper_mg_l),
        source=row.source,
        confidence_pct=_dec_to_float(row.confidence_pct),
        reviewer_notes=row.reviewer_notes,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _get_medication_by_name_or_404(name: str, session: Session) -> Medication:
    med = session.exec(select(Medication).where(Medication.name == name)).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    return med


def _get_medication_by_id_or_404(medication_id: str, session: Session) -> Medication:
    med = session.get(Medication, medication_id)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")
    return med


def _get_window_review_by_med_id(
    medication_id: str, session: Session
) -> MedicationTherapeuticWindowReview | None:
    return session.exec(
        select(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.medication_id == medication_id
        )
    ).first()


@router.get("/")
def list_medications(session: Session = Depends(get_session)):
    return session.exec(select(Medication)).all()


@router.get("/simulation-ready")
def list_simulation_ready_medications(session: Session = Depends(get_session)):
    meds = session.exec(select(Medication)).all()
    reviews = session.exec(select(MedicationTherapeuticWindowReview)).all()
    approved_ids = {
        str(r.medication_id)
        for r in reviews
        if r.status == "approved" and r.lower_mg_l is not None and r.upper_mg_l is not None
    }
    return [med for med in meds if str(med.id) in approved_ids]


@router.get("/{name}")
def get_medication_by_name(name: str, session: Session = Depends(get_session)):
    return _get_medication_by_name_or_404(name, session)


@router.post("/")
def create_medication(body: MedicationCreate, session: Session = Depends(get_session)):
    data = _normalize_medication_payload(body.model_dump(exclude_none=True))
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
    med = _get_medication_by_name_or_404(name, session)

    updates = _normalize_medication_payload(body.model_dump(exclude_none=True))

    for key, value in updates.items():
        setattr(med, key, value)

    session.add(med)
    session.commit()
    session.refresh(med)
    return med


@router.delete("/{name}")
def delete_medication(name: str, session: Session = Depends(get_session)):
    med = _get_medication_by_name_or_404(name, session)

    removed_simulations = session.exec(
        delete(Simulation).where(Simulation.medication_id == med.id)
    ).rowcount or 0
    removed_links = session.exec(
        delete(PatientMedicationLink).where(PatientMedicationLink.medication_id == med.id)
    ).rowcount or 0
    removed_reviews = session.exec(
        delete(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.medication_id == med.id
        )
    ).rowcount or 0
    session.exec(delete(Medication).where(Medication.id == med.id))
    session.commit()

    return {
        "deleted": True,
        "name": name,
        "removed_reviews": removed_reviews,
        "removed_links": removed_links,
        "removed_simulations": removed_simulations,
    }


@router.get("/{medication_id}/window-review", response_model=WindowReviewResponse)
def get_window_review(medication_id: str, session: Session = Depends(get_session)):
    med = _get_medication_by_id_or_404(medication_id, session)
    row = _get_window_review_by_med_id(str(med.id), session)
    if row is None:
        row = MedicationTherapeuticWindowReview(
            medication_id=med.id,
            status="manual_required",
            source="none",
            confidence_pct=_float_to_dec(0.0),
            updated_at=datetime.now(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
    return _to_review_response(row)


@router.post("/{medication_id}/window-review/approve", response_model=WindowReviewResponse)
def approve_window_review(medication_id: str, session: Session = Depends(get_session)):
    med = _get_medication_by_id_or_404(medication_id, session)
    row = _get_window_review_by_med_id(str(med.id), session)
    if row is None:
        raise HTTPException(status_code=400, detail="No proposal exists to approve")
    if row.lower_mg_l is None or row.upper_mg_l is None:
        raise HTTPException(status_code=400, detail="No therapeutic window values to approve")
    if float(row.upper_mg_l) <= float(row.lower_mg_l):
        raise HTTPException(status_code=400, detail="Invalid therapeutic window values")
    row.status = "approved"
    row.updated_at = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)

    med.therapeutic_window_lower_mg_l = row.lower_mg_l
    med.therapeutic_window_upper_mg_l = row.upper_mg_l
    session.add(med)
    session.commit()
    return _to_review_response(row)


@router.post("/{medication_id}/window-review/reject", response_model=WindowReviewResponse)
def reject_window_review(
    medication_id: str,
    body: WindowRejectRequest,
    session: Session = Depends(get_session),
):
    med = _get_medication_by_id_or_404(medication_id, session)
    row = _get_window_review_by_med_id(str(med.id), session)
    if row is None:
        row = MedicationTherapeuticWindowReview(medication_id=med.id)

    manual_low = body.manual_lower_mg_l
    manual_high = body.manual_upper_mg_l
    if manual_low is not None or manual_high is not None:
        if manual_low is None or manual_high is None:
            raise HTTPException(status_code=400, detail="Provide both manual lower and upper")
        if manual_low < 0 or manual_high <= manual_low:
            raise HTTPException(status_code=400, detail="Invalid manual therapeutic window")
        row.lower_mg_l = _float_to_dec(manual_low)
        row.upper_mg_l = _float_to_dec(manual_high)
        row.source = "manual-entry"
        row.confidence_pct = _float_to_dec(100.0)
        row.status = "proposed"
    else:
        row.status = "manual_required"
        row.lower_mg_l = None
        row.upper_mg_l = None
        row.source = "rejected-no-manual"

    row.reviewer_notes = body.notes
    row.updated_at = datetime.now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_review_response(row)


@router.get("/window-review/queue", response_model=list[WindowReviewResponse])
def list_window_review_queue(session: Session = Depends(get_session)):
    rows = session.exec(
        select(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.status.in_(
                ["manual_required", "rejected"]
            )
        )
    ).all()
    return [_to_review_response(r) for r in rows]
