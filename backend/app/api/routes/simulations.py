from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from app.models import AcceptedSimulation
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.patient_auth import get_current_patient
from ...core.security import decryptData
from ...models import (
    Clinician,
    Condition,
    Medication,
    Patient,
    PatientClinicalFactors,
    PatientConditionLink,
    PatientCurrentMedication,
    PatientVitalSigns,
    Simulation,
)
from ...pharmacokinetics import (
    evaluate_therapeutic_window,
    resolve_therapeutic_window_for_medication,
    simulate_and_store,
)
from ...ade_screening import screen_medication_safety

router = APIRouter(
    prefix="/sims",
    tags=["sims"],
)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _decrypt_or_raw(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return decryptData(value)
    except Exception:
        return value


class RunSimulationRequest(BaseModel):
    patient_id: str
    medication_id: str
    dose_mg: float = Field(..., gt=0)
    interval_hr: float = Field(..., gt=0)
    num_doses: int = Field(..., ge=1)
    absorption_rate_hr: Optional[float] = Field(
        None,
        gt=0,
        description="ka; if not set, treated as IV/instant.",
    )
    dt_hr: float = Field(0.1, gt=0, description="Simulation step (hours).")


class RunSimulationResponse(BaseModel):
    id: str
    patient_id: str
    medication_id: str

    dose_mg: Optional[float]
    interval_hr: Optional[float]
    duration_hr: Optional[float]

    cmax_mg_l: Optional[float]
    cmin_mg_l: Optional[float]
    auc_mg_h_l: Optional[float]

    flag_too_high: bool
    flag_too_low: bool

    patient_context: Dict[str, Any]
    ade_screening: Dict[str, Any]
    therapeutic_window: Dict[str, Any]
    therapeutic_eval: Dict[str, Any]
    params_used: Dict[str, Any]
    times_hr: List[float]
    conc_mg_per_L: List[float]


class ShareSimulationRequest(BaseModel):
    patient_email: EmailStr
    clinician_email: EmailStr


class SharedSimulationSummary(BaseModel):
    id: str
    medication_name: Optional[str]
    created_at: Optional[str]
    shared_at: Optional[str]
    shared_by: Optional[str]
    dose_mg: Optional[float]
    interval_hr: Optional[float]
    duration_hr: Optional[float]
    cmax_mg_l: Optional[float]
    cmin_mg_l: Optional[float]
    auc_mg_h_l: Optional[float]
    flag_too_high: Optional[bool]
    flag_too_low: Optional[bool]
    therapeutic_window: Optional[Dict[str, Any]]
    therapeutic_eval: Optional[Dict[str, Any]]


class SharedSimulationDetail(SharedSimulationSummary):
    params_used: Dict[str, Any]
    times_hr: List[float]
    conc_mg_per_L: List[float]
    patient_context: Dict[str, Any]
    ade_screening: Dict[str, Any]


def _parse_uuid(value: str, detail: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=detail)


def _find_patient_by_email(session: Session, email: str) -> Optional[Patient]:
    target = email.strip().lower()
    patients = session.exec(select(Patient)).all()
    for patient in patients:
        try:
            candidate = _decrypt_or_raw(patient.email)
        except Exception:
            candidate = patient.email
        if isinstance(candidate, str) and candidate.strip().lower() == target:
            return patient
    return None


def _shared_payload(sim: Simulation, med_name: Optional[str]) -> SharedSimulationDetail:
    sim_results: Dict[str, Any] = dict(sim.sim_results or {})
    shared_meta = sim_results.get("shared", {}) or {}
    return SharedSimulationDetail(
        id=str(sim.id),
        medication_name=med_name,
        created_at=sim.created_at.isoformat() if sim.created_at else None,
        shared_at=shared_meta.get("sent_at"),
        shared_by=shared_meta.get("sent_by"),
        dose_mg=float(sim.dose_mg) if sim.dose_mg is not None else None,
        interval_hr=float(sim.interval_hr) if sim.interval_hr is not None else None,
        duration_hr=float(sim.duration_hr) if sim.duration_hr is not None else None,
        cmax_mg_l=float(sim.cmax_mg_l) if sim.cmax_mg_l is not None else None,
        cmin_mg_l=float(sim.cmin_mg_l) if sim.cmin_mg_l is not None else None,
        auc_mg_h_l=float(sim.auc_mg_h_l) if sim.auc_mg_h_l is not None else None,
        flag_too_high=sim.flag_too_high,
        flag_too_low=sim.flag_too_low,
        therapeutic_window=sim_results.get("therapeutic_window") or {},
        therapeutic_eval=sim_results.get("therapeutic_eval") or {},
        params_used=sim_results.get("params_used") or {},
        times_hr=sim_results.get("times_hr", []) or [],
        conc_mg_per_L=sim_results.get("conc_mg_per_L", []) or [],
        patient_context=sim_results.get("patient_context") or {},
        ade_screening=sim_results.get("ade_screening") or {},
    )


@router.post("/run", response_model=RunSimulationResponse)
def run_simulation(
    payload: RunSimulationRequest,
    session: Session = Depends(get_session),
):
    pat = session.exec(
        select(Patient).where(Patient.id == payload.patient_id)
    ).first()
    if pat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    med = session.exec(
        select(Medication).where(Medication.id == payload.medication_id)
    ).first()
    if med is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found",
        )

    sim: Simulation = simulate_and_store(
        session=session,
        patient_id=str(pat.id),
        medication_id=str(med.id),
        dose_mg=payload.dose_mg,
        interval_hr=payload.interval_hr,
        num_doses=payload.num_doses,
        absorption_rate_hr=payload.absorption_rate_hr,
        dt_hr=payload.dt_hr,
    )

    sim_results: Dict[str, Any] = sim.sim_results or {}
    times_hr: List[float] = sim_results.get("times_hr", []) or []
    conc_mg_per_L: List[float] = sim_results.get("conc_mg_per_L", []) or []
    params_used: Dict[str, Any] = sim_results.get("params_used", {}) or {}
    factors = session.exec(
        select(PatientClinicalFactors).where(PatientClinicalFactors.patient_id == pat.id)
    ).first()
    vitals = session.exec(
        select(PatientVitalSigns).where(PatientVitalSigns.patient_id == pat.id)
    ).first()
    condition_links = session.exec(
        select(PatientConditionLink).where(PatientConditionLink.patient_id == pat.id)
    ).all()
    condition_names: list[str] = []
    for link in condition_links:
        condition = session.get(Condition, link.condition_id)
        if condition and condition.name:
            condition_names.append(condition.name)
    current_meds = session.exec(
        select(PatientCurrentMedication).where(PatientCurrentMedication.patient_id == pat.id)
    ).all()
    current_medication_names = [m.name for m in current_meds if m.name]

    lower, upper, targets, window_source = resolve_therapeutic_window_for_medication(session, med)

    therapeutic_eval = evaluate_therapeutic_window(
        times=times_hr,
        conc=conc_mg_per_L,
        therapeutic_min_mg_per_L=lower,
        therapeutic_max_mg_per_L=upper,
        t_start_hr=0.0,
        t_end_hr=payload.interval_hr * payload.num_doses,
        targets=targets,
    )

    patient_context: Dict[str, Any] = {
        "patient_id": str(pat.id),
        "age": pat.age,
        "sex": pat.sex,
        "weight_kg": _safe_float(pat.weight_kg),
        "serum_creatinine_mg_dl": _safe_float(pat.serum_creatinine_mg_dl),
        "creatinine_clearance_ml_min": _safe_float(pat.creatinine_clearance_ml_min),
        "ckd_stage": _decrypt_or_raw(pat.ckd_stage),
        "height_cm": _safe_float(factors.height_cm) if factors else None,
        "is_pregnant": factors.is_pregnant if factors else None,
        "pregnancy_trimester": factors.pregnancy_trimester if factors else None,
        "is_breastfeeding": factors.is_breastfeeding if factors else None,
        "liver_disease_status": factors.liver_disease_status if factors else None,
        "albumin_g_dl": _safe_float(factors.albumin_g_dl) if factors else None,
        "systolic_bp_mm_hg": vitals.systolic_bp_mm_hg if vitals else None,
        "diastolic_bp_mm_hg": vitals.diastolic_bp_mm_hg if vitals else None,
        "heart_rate_bpm": vitals.heart_rate_bpm if vitals else None,
        "conditions": sorted(list(set(condition_names))),
        "current_medications": sorted(list(set(current_medication_names))),
    }
    ade_screening = screen_medication_safety(med.name, patient_context)

    sim.flag_too_high = therapeutic_eval["pct_above"] > therapeutic_eval["target_above_pct"]
    sim.flag_too_low = therapeutic_eval["pct_below"] > therapeutic_eval["target_below_pct"]

    sim_results["therapeutic_eval"] = therapeutic_eval
    sim_results["patient_context"] = patient_context
    sim_results["ade_screening"] = ade_screening
    sim_results["therapeutic_window"] = {
        "lower_mg_l": lower,
        "upper_mg_l": upper,
        "source": window_source,
    }
    sim.sim_results = sim_results

    session.add(sim)
    session.commit()
    session.refresh(sim)
    
    pat.last_simulation_at = datetime.now(timezone.utc)
    session.add(pat)
    session.commit()

    chart_times = times_hr[:2000]
    chart_conc = conc_mg_per_L[:2000]

    return RunSimulationResponse(
        id=str(sim.id),
        patient_id=str(sim.patient_id),
        medication_id=str(sim.medication_id),
        dose_mg=float(sim.dose_mg) if sim.dose_mg is not None else None,
        interval_hr=float(sim.interval_hr) if sim.interval_hr is not None else None,
        duration_hr=float(sim.duration_hr) if sim.duration_hr is not None else None,
        cmax_mg_l=float(sim.cmax_mg_l) if sim.cmax_mg_l is not None else None,
        cmin_mg_l=float(sim.cmin_mg_l) if sim.cmin_mg_l is not None else None,
        auc_mg_h_l=float(sim.auc_mg_h_l) if sim.auc_mg_h_l is not None else None,
        flag_too_high=sim.flag_too_high,
        flag_too_low=sim.flag_too_low,
        patient_context=patient_context,
        ade_screening=ade_screening,
        therapeutic_window={
            "lower_mg_l": lower,
            "upper_mg_l": upper,
            "source": window_source,
        },
        therapeutic_eval=therapeutic_eval,
        params_used=params_used,
        times_hr=chart_times,
        conc_mg_per_L=chart_conc,
    )


@router.post("/share/{simulation_id}")
def share_simulation(
    simulation_id: str,
    payload: ShareSimulationRequest,
    session: Session = Depends(get_session),
):
    sim_id = _parse_uuid(simulation_id, "Invalid simulation ID")
    simulation = session.get(Simulation, sim_id)
    if not simulation:
        raise HTTPException(status_code=404, detail="Simulation not found")

    clinician = session.exec(
        select(Clinician).where(Clinician.email == payload.clinician_email)
    ).first()
    if not clinician:
        raise HTTPException(status_code=404, detail="Clinician not found")

    patient = _find_patient_by_email(session, payload.patient_email)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if str(simulation.patient_id) != str(patient.id):
        raise HTTPException(
            status_code=400,
            detail="Simulation patient does not match target patient email",
        )

    # Keep only one active shared simulation per patient so the patient inbox
    # reflects the single simulation the clinician intentionally sent most recently.
    patient_sims = session.exec(
        select(Simulation).where(Simulation.patient_id == patient.id)
    ).all()
    for other in patient_sims:
        if str(other.id) == str(simulation.id):
            continue
        other_results: Dict[str, Any] = dict(other.sim_results or {})
        shared_meta = dict(other_results.get("shared") or {})
        if shared_meta.get("sent"):
            shared_meta["sent"] = False
            shared_meta["superseded_at"] = datetime.now(timezone.utc).isoformat()
            other_results["shared"] = shared_meta
            other.sim_results = other_results
            session.add(other)

    sim_results: Dict[str, Any] = dict(simulation.sim_results or {})
    sim_results["shared"] = {
        "sent": True,
        "patient_email": payload.patient_email.strip().lower(),
        "sent_by": payload.clinician_email.strip().lower(),
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    simulation.sim_results = sim_results
    session.add(simulation)
    session.commit()

    return {"ok": True, "simulation_id": str(simulation.id)}


@router.get("/me/shared", response_model=List[SharedSimulationSummary])
def list_shared_simulations_for_patient(
    user: dict = Depends(get_current_patient),
    session: Session = Depends(get_session),
):
    patient_id = _parse_uuid(user["patient_id"], "Invalid patient token")
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sims = session.exec(
        select(Simulation).where(Simulation.patient_id == patient.id)
    ).all()

    results: List[SharedSimulationSummary] = []
    for sim in sims:
        sim_results: Dict[str, Any] = sim.sim_results or {}
        shared_meta = sim_results.get("shared") or {}
        if not shared_meta.get("sent"):
            continue
        med = session.get(Medication, sim.medication_id)
        full = _shared_payload(sim, med.name if med else None)
        results.append(SharedSimulationSummary(**full.model_dump()))

    results.sort(key=lambda row: row.shared_at or "", reverse=True)
    return results


@router.get("/me/shared/{simulation_id}", response_model=SharedSimulationDetail)
def get_shared_simulation_for_patient(
    simulation_id: str,
    user: dict = Depends(get_current_patient),
    session: Session = Depends(get_session),
):
    patient_id = _parse_uuid(user["patient_id"], "Invalid patient token")
    sim_id = _parse_uuid(simulation_id, "Invalid simulation ID")

    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sim = session.get(Simulation, sim_id)
    if not sim or str(sim.patient_id) != str(patient.id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    sim_results: Dict[str, Any] = sim.sim_results or {}
    shared_meta = sim_results.get("shared") or {}
    if not shared_meta.get("sent"):
        raise HTTPException(status_code=403, detail="Simulation is not shared")

    med = session.get(Medication, sim.medication_id)
    return _shared_payload(sim, med.name if med else None)

@router.post("/accept")
def accept_simulation(
    patient_id: UUID,
    medication_id: UUID,
    simulation_id: UUID,
    session: Session = Depends(get_session)
):
    existing = session.exec(
        select(AcceptedSimulation).where(
            AcceptedSimulation.patient_id == patient_id,
            AcceptedSimulation.medication_id == medication_id
        )
    ).first()

    if existing:
        existing.simulation_id = simulation_id
        existing.accepted_at = datetime.now()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    accepted = AcceptedSimulation(
        patient_id=patient_id,
        medication_id=medication_id,
        simulation_id=simulation_id
    )

    session.add(accepted)
    session.commit()
    session.refresh(accepted)

    return accepted

@router.get("/accepted/{patient_id}/{medication_id}")
def get_accepted_simulation(
    patient_id: UUID,
    medication_id: UUID,
    session: Session = Depends(get_session)
):
    accepted = session.exec(
        select(AcceptedSimulation).where(
            AcceptedSimulation.patient_id == patient_id,
            AcceptedSimulation.medication_id == medication_id
        )
    ).first()

    if not accepted:
        return {"message": "No accepted simulation found"}

    return accepted
