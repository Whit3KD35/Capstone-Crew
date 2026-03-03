from __future__ import annotations

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ...core.db import get_session
from ...core.security import decryptData
from ...models import (
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
    therapeutic_window: Dict[str, Any]
    therapeutic_eval: Dict[str, Any]
    params_used: Dict[str, Any]
    times_hr: List[float]
    conc_mg_per_L: List[float]


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

    sim.flag_too_high = therapeutic_eval["pct_above"] > therapeutic_eval["target_above_pct"]
    sim.flag_too_low = therapeutic_eval["pct_below"] > therapeutic_eval["target_below_pct"]

    sim_results["therapeutic_eval"] = therapeutic_eval
    sim_results["patient_context"] = patient_context
    sim_results["therapeutic_window"] = {
        "lower_mg_l": lower,
        "upper_mg_l": upper,
        "source": window_source,
    }
    sim.sim_results = sim_results

    session.add(sim)
    session.commit()
    session.refresh(sim)

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
