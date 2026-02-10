from __future__ import annotations

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ...core.db import get_session
from ...models import Patient, Medication, Simulation
from ...pharmacokinetics import simulate_and_store

router = APIRouter(
    prefix="/sims",
    tags=["sims"],
)

# Therapeutic window helper
def evaluate_therapeutic_window(
    times_hr: List[float],
    conc_mg_per_L: List[float],
    lower_mg_per_L: float,
    upper_mg_per_L: float,
) -> Dict[str, Any]:
    """
    Evaluate % time BELOW / WITHIN / ABOVE [lower, upper] mg/L.

    - Ignores the very long terminal tail by only integrating over the
      "active" period where concentration >= 10% of the lower bound.
    - Uses a simple midpoint rule between adjacent samples.
    """
    if (
        not times_hr
        or not conc_mg_per_L
        or len(times_hr) != len(conc_mg_per_L)
        or lower_mg_per_L <= 0
        or upper_mg_per_L <= lower_mg_per_L
    ):
        return {
            "alerts": ["Insufficient data to evaluate therapeutic window."],
            "off_score": 0.0,
            "pct_above": 0.0,
            "pct_below": 0.0,
            "pct_within": 0.0,
            "ade_risk_level": "UNKNOWN",
            "time_within_hr": 0.0,
            "time_above_hr": 0.0,
            "time_below_hr": 0.0,
        }

    # Determine active evaluation window by trimming tail
    threshold = 0.1 * lower_mg_per_L  # 10% of lower bound
    active_indices = [i for i, c in enumerate(conc_mg_per_L) if c >= threshold]

    if not active_indices:
        total_time = times_hr[-1] - times_hr[0]
        total_time = max(total_time, 1e-9)
        return {
            "alerts": [
                f"Concentration never reached 10% of lower bound "
                f"({threshold:.2f} mg/L). Essentially always below range."
            ],
            "off_score": 100.0,
            "pct_above": 0.0,
            "pct_below": 100.0,
            "pct_within": 0.0,
            "ade_risk_level": "HIGH",
            "time_within_hr": 0.0,
            "time_above_hr": 0.0,
            "time_below_hr": total_time,
        }

    start_idx = active_indices[0]
    end_idx = active_indices[-1]

    eval_start = times_hr[start_idx]
    eval_end = times_hr[end_idx]
    total_time = eval_end - eval_start
    total_time = max(total_time, 1e-9)

    time_within = 0.0
    time_above = 0.0
    time_below = 0.0

    # Integrate only over [start_idx, end_idx]
    for i in range(start_idx, end_idx):
        t0 = times_hr[i]
        t1 = times_hr[i + 1]
        dt = t1 - t0
        if dt <= 0:
            continue

        c_mid = 0.5 * (conc_mg_per_L[i] + conc_mg_per_L[i + 1])

        if c_mid < lower_mg_per_L:
            time_below += dt
        elif c_mid > upper_mg_per_L:
            time_above += dt
        else:
            time_within += dt

    pct_within = 100.0 * time_within / total_time
    pct_above = 100.0 * time_above / total_time
    pct_below = 100.0 * time_below / total_time

    # Risk heuristic
    if pct_above > 30.0 or pct_below > 50.0:
        risk = "HIGH"
    elif pct_above > 10.0 or pct_below > 30.0:
        risk = "MODERATE"
    elif pct_above > 0.0 or pct_below > 0.0:
        risk = "LOW"
    else:
        risk = "NONE"

    alerts: List[str] = []
    alerts.append(
        f"Evaluated between t = {eval_start:.1f}–{eval_end:.1f} h "
        f"for window [{lower_mg_per_L:.2f}, {upper_mg_per_L:.2f}] mg/L."
    )
    if time_above > 0:
        alerts.append(
            f"Above therapeutic range for {time_above:.1f} h "
            f"({pct_above:.1f}% of evaluated time)."
        )
    if time_below > 0:
        alerts.append(
            f"Below therapeutic range for {time_below:.1f} h "
            f"({pct_below:.1f}% of evaluated time)."
        )
    if time_within > 0:
        alerts.append(
            f"Within therapeutic range for {time_within:.1f} h "
            f"({pct_within:.1f}% of evaluated time)."
        )

    off_score = pct_above + pct_below

    return {
        "alerts": alerts,
        "off_score": off_score,
        "pct_above": pct_above,
        "pct_below": pct_below,
        "pct_within": pct_within,
        "ade_risk_level": risk,
        "time_within_hr": time_within,
        "time_above_hr": time_above,
        "time_below_hr": time_below,
    }


# Request / response models
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

    therapeutic_eval: Dict[str, Any]
    times_hr: List[float]
    conc_mg_per_L: List[float]

# Route
@router.post("/run", response_model=RunSimulationResponse)
def run_simulation(
    payload: RunSimulationRequest,
    session: Session = Depends(get_session),
):
    # Validate patient / medication ID
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

    # Run & store base PK simulation
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

    lower = getattr(med, "therapeutic_window_lower_mg_l", None)
    upper = getattr(med, "therapeutic_window_upper_mg_l", None)

    # global fallback if not set on the drug
    if lower is None or upper is None or lower <= 0 or upper <= lower:
        lower = 1.0   # mg/L
        upper = 10.0  # mg/L

    therapeutic_eval = evaluate_therapeutic_window(
        times_hr=times_hr,
        conc_mg_per_L=conc_mg_per_L,
        lower_mg_per_L=lower,
        upper_mg_per_L=upper,
    )

    # Update flags & persist updated results
    sim.flag_too_high = therapeutic_eval["pct_above"] > 0.0
    sim.flag_too_low = therapeutic_eval["pct_below"] > 0.0

    sim_results["therapeutic_eval"] = therapeutic_eval
    sim.sim_results = sim_results

    session.add(sim)
    session.commit()
    session.refresh(sim)

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
        therapeutic_eval=therapeutic_eval,
        times_hr=times_hr,
        conc_mg_per_L=conc_mg_per_L,
    )
