from __future__ import annotations
from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session
from ...core.db import get_session

from ...pharmacokinetics import (
    fetch_drug_pharmacokinetics,
    predict_concentration_timecourse,
    evaluate_therapeutic_window,
    compute_creatinine_clearance,
)

try:
    from ...models import Pharmacokinetic
    HAS_PK_MODEL = True
except Exception:
    Pharmacokinetic = None
    HAS_PK_MODEL = False

router = APIRouter(prefix="/pk", tags=["Pharmacokinetics"])


# Schemas
class SimulateRequest(BaseModel):
    drug_name: Optional[str] = Field(None, description="If provided, fetch PK params for this drug first.")
    half_life_hr: Optional[float] = None
    clearance_L_per_hr: Optional[float] = None
    Vd_L: Optional[float] = None
    bioavailability: Optional[float] = Field(None, ge=0.0, le=1.0)

    dose_mg: float = Field(..., gt=0)
    interval_hr: float = Field(..., gt=0, description="Dosing interval τ (hours).")
    num_doses: int = Field(..., ge=1)
    absorption_rate_hr: Optional[float] = Field(None, gt=0, description="ka; if not set, treated as IV/instant.")
    body_weight_kg: Optional[float] = Field(None, gt=0)
    t_end_hr: Optional[float] = Field(None, gt=0)
    dt_hr: float = Field(0.1, gt=0, description="Simulation step (hours).")

class SimulateResponse(BaseModel):
    times_hr: List[float]
    conc_mg_per_L: List[float]
    params_used: dict

class TherapeuticWindowRequest(BaseModel):
    times_hr: Annotated[List[float], Field(min_length=2)]
    conc_mg_per_L: Annotated[List[float], Field(min_length=2)]
    therapeutic_min_mg_per_L: float = Field(..., ge=0)
    therapeutic_max_mg_per_L: float = Field(..., gt=0)

class TherapeuticWindowResponse(BaseModel):
    pct_below: float
    pct_within: float
    pct_above: float
    time_below_hr: float
    time_within_hr: float
    time_above_hr: float
    alerts: List[str]

class CreatinineClearanceRequest(BaseModel):
    age: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    serum_creatinine_mg_dl: float = Field(..., gt=0)
    sex: str = Field(..., description="M/F")


# Endpoints
@router.get("/fetch", summary="Fetch And Upsert")
def fetch_and_upsert(
    name: str = Query(..., description="Medication name, e.g., 'Warfarin'"),
    upsert: bool = Query(False, description="If true, persist numeric PK into DB (best-effort)."),
    db: Session = Depends(get_session),
):
    pk = fetch_drug_pharmacokinetics(name)

    if upsert and HAS_PK_MODEL:
        try:
            entry = Pharmacokinetic(
                name=name.lower(),
                half_life_hr=pk.get("half_life_hr"),
                clearance_L_per_hr=pk.get("clearance_L_per_hr"),
                Vd_L=pk.get("Vd_L"),
                bioavailability=pk.get("bioavailability"),
                sources=pk.get("sources"),
            )
            db.add(entry)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Upsert failed: {e}")

    return pk


@router.post("/simulate", response_model=SimulateResponse, summary="Simulate")
def simulate(req: SimulateRequest):
    params = {"half_life_hr": None, "clearance_L_per_hr": None, "Vd_L": None, "bioavailability": None}
    if req.drug_name:
        fetched = fetch_drug_pharmacokinetics(req.drug_name)
        params.update({k: fetched.get(k) for k in params.keys()})

    overrides = {
        "half_life_hr": req.half_life_hr,
        "clearance_L_per_hr": req.clearance_L_per_hr,
        "Vd_L": req.Vd_L,
        "bioavailability": req.bioavailability,
    }
    for k, v in overrides.items():
        if v is not None:
            params[k] = v

    try:
        times, conc = predict_concentration_timecourse(
            drug_params=params,
            dosing_mg=req.dose_mg,
            dosing_interval_hr=req.interval_hr,
            num_doses=req.num_doses,
            absorption_rate_hr=req.absorption_rate_hr,
            body_weight_kg=req.body_weight_kg,
            t_end_hr=req.t_end_hr,
            dt_hr=req.dt_hr,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    if len(times) > 5000:
        times = times[:5000]
        conc = conc[:5000]

    return SimulateResponse(times_hr=times, conc_mg_per_L=conc, params_used=params)


@router.post("/therapeutic-window", response_model=TherapeuticWindowResponse, summary="Score Window")
def therapeutic_window(req: TherapeuticWindowRequest):
    if len(req.times_hr) != len(req.conc_mg_per_L):
        raise HTTPException(status_code=400, detail="times_hr and conc_mg_per_L lengths must match")

    res = evaluate_therapeutic_window(
        times=list(req.times_hr),
        conc=list(req.conc_mg_per_L),
        therapeutic_min_mg_per_L=req.therapeutic_min_mg_per_L,
        therapeutic_max_mg_per_L=req.therapeutic_max_mg_per_L,
    )
    return TherapeuticWindowResponse(**res)


@router.post("/creatinine-clearance", summary="Cg")
def creatinine_clearance(req: CreatinineClearanceRequest):
    try:
        crcl = compute_creatinine_clearance(
            age=req.age,
            weight_kg=req.weight_kg,
            serum_creatinine_mg_dl=req.serum_creatinine_mg_dl,
            sex=req.sex,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {"creatinine_clearance_ml_min": crcl}
