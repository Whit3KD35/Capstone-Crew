from __future__ import annotations
from typing import Optional, List, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ...core.db import get_session
from ...models import Medication
from ...pharmacokinetics import (
    TherapeuticTargets,
    compute_prediction_accuracy_metrics,
    fetch_drug_pharmacokinetics,
    list_supported_tdm_drugs,
    predict_concentration_timecourse,
    evaluate_therapeutic_window,
    compute_creatinine_clearance,
    build_window_review_preview,
    upsert_window_review_proposal,
    _float_to_dec,
)

router = APIRouter(prefix="/pk", tags=["Pharmacokinetics"])

class SimulateRequest(BaseModel):
    drug_name: Optional[str] = Field(
        None,
        description="If provided, fetch PK params for this drug first.",
    )
    half_life_hr: Optional[float] = None
    clearance_L_per_hr: Optional[float] = None
    Vd_L: Optional[float] = None
    bioavailability: Optional[float] = Field(None, ge=0.0, le=1.0)

    dose_mg: float = Field(..., gt=0)
    interval_hr: float = Field(..., gt=0, description="Dosing interval τ (hours).")
    num_doses: int = Field(..., ge=1)
    absorption_rate_hr: Optional[float] = Field(
        None,
        gt=0,
        description="ka; if not set, treated as IV/instant.",
    )
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
    target_max_pct_below: Optional[float] = Field(None, ge=0)
    target_max_pct_above: Optional[float] = Field(None, ge=0)
    target_min_pct_within: Optional[float] = Field(None, ge=0, le=100)

class TherapeuticWindowResponse(BaseModel):
    pct_below: float
    pct_within: float
    pct_above: float
    time_below_hr: float
    time_within_hr: float
    time_above_hr: float
    alerts: List[str]

    target_below_pct: float
    target_above_pct: float
    target_within_pct: float

    below_gap_pct: float
    above_gap_pct: float
    within_gap_pct: float

    off_score: float
    ade_risk_level: str

class CreatinineClearanceRequest(BaseModel):
    age: float = Field(..., gt=0)
    weight_kg: float = Field(..., gt=0)
    serum_creatinine_mg_dl: float = Field(..., gt=0)
    sex: str = Field(..., description="M/F")


class AccuracyMetricsRequest(BaseModel):
    observed_conc_mg_per_L: Annotated[List[float], Field(min_length=1)]
    predicted_conc_mg_per_L: Annotated[List[float], Field(min_length=1)]


class AccuracyMetricsResponse(BaseModel):
    n_total: float
    n_nonzero_observed: float
    mae: float
    rmse: float
    mpe_pct: float
    mape_pct: float
    p20_pct: float
    p30_pct: float


@router.get("/supported-drugs", summary="Supported TDM Drugs")
def supported_drugs(db: Session = Depends(get_session)):
    return {
        "supported_tdm_drugs": list_supported_tdm_drugs(db),
        "note": "Windows are concentration targets in mg/L for drugs with established TDM use.",
    }

@router.get("/fetch", summary="Fetch And Upsert")
def fetch_and_upsert(
    name: str = Query(..., description="Medication name, e.g., 'Warfarin'"),
    upsert: bool = Query(
        False,
        description="If true, persist PK into Medication table (best-effort).",
    ),
    include_raw: bool = Query(
        False,
        description="If true, include full raw source text blocks (can be very large).",
    ),
    db: Session = Depends(get_session),
):
    pk = fetch_drug_pharmacokinetics(name)
    med: Medication | None = None

    if upsert:
        try:
            med = db.exec(
                select(Medication).where(Medication.name == name)
            ).first()
            if med is None:
                med = Medication(name=name)

            if pk.get("half_life_hr") is not None:
                med.half_life_hr = _float_to_dec(pk["half_life_hr"])

            if pk.get("bioavailability") is not None:
                med.bioavailability_f = _float_to_dec(pk["bioavailability"])

            if pk.get("clearance_raw_value") is not None:
                med.clearance_raw_value = _float_to_dec(pk["clearance_raw_value"])
                med.clearance_raw_unit = pk.get("clearance_raw_unit")

            if pk.get("Vd_raw_value") is not None:
                med.volume_of_distribution_raw_value = _float_to_dec(pk["Vd_raw_value"])
                med.volume_of_distribution_raw_unit = pk.get("Vd_raw_unit")
            if (
                med.therapeutic_window_lower_mg_l is None
                and pk.get("therapeutic_window_lower_mg_l") is not None
            ):
                med.therapeutic_window_lower_mg_l = _float_to_dec(
                    float(pk["therapeutic_window_lower_mg_l"])
                )
            if (
                med.therapeutic_window_upper_mg_l is None
                and pk.get("therapeutic_window_upper_mg_l") is not None
            ):
                med.therapeutic_window_upper_mg_l = _float_to_dec(
                    float(pk["therapeutic_window_upper_mg_l"])
                )

            db.add(med)
            db.commit()
            db.refresh(med)
            upsert_window_review_proposal(db, med, fetched_pk=pk)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Upsert failed: {e}")
    else:
        med = db.exec(select(Medication).where(Medication.name == name)).first()

    pk["window_review"] = build_window_review_preview(
        session=db,
        med_name=name,
        med=med,
        fetched_pk=pk,
    )

    if include_raw:
        return pk
    return _summarize_source_payload(pk)


def _summarize_source_payload(pk: dict[str, Any]) -> dict[str, Any]:
    summary = dict(pk)
    sources = pk.get("sources", {})
    summarized_sources: dict[str, Any] = {}
    for source_name, source_val in sources.items():
        if isinstance(source_val, str):
            summarized_sources[source_name] = {
                "has_raw_text": len(source_val.strip()) > 0,
                "raw_char_count": len(source_val),
            }
        else:
            summarized_sources[source_name] = {
                "has_raw_text": False,
                "raw_char_count": 0,
            }
    summary["sources"] = summarized_sources
    return summary


@router.post("/simulate", response_model=SimulateResponse, summary="Simulate")
def simulate(req: SimulateRequest):
    params = {
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
    }

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

    return SimulateResponse(
        times_hr=times,
        conc_mg_per_L=conc,
        params_used=params,
    )


@router.post(
    "/therapeutic-window",
    response_model=TherapeuticWindowResponse,
    summary="Score Window",
)
def therapeutic_window(req: TherapeuticWindowRequest):
    if len(req.times_hr) != len(req.conc_mg_per_L):
        raise HTTPException(
            status_code=400,
            detail="times_hr and conc_mg_per_L lengths must match",
        )

    targets = TherapeuticTargets(
        max_pct_below=req.target_max_pct_below if req.target_max_pct_below is not None else 20.0,
        max_pct_above=req.target_max_pct_above if req.target_max_pct_above is not None else 5.0,
        min_pct_within=req.target_min_pct_within if req.target_min_pct_within is not None else 50.0,
    )

    res = evaluate_therapeutic_window(
        times=list(req.times_hr),
        conc=list(req.conc_mg_per_L),
        therapeutic_min_mg_per_L=req.therapeutic_min_mg_per_L,
        therapeutic_max_mg_per_L=req.therapeutic_max_mg_per_L,
        targets=targets,
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


@router.post("/accuracy-metrics", response_model=AccuracyMetricsResponse, summary="Prediction Accuracy")
def accuracy_metrics(req: AccuracyMetricsRequest):
    if len(req.observed_conc_mg_per_L) != len(req.predicted_conc_mg_per_L):
        raise HTTPException(
            status_code=400,
            detail="observed_conc_mg_per_L and predicted_conc_mg_per_L lengths must match",
        )
    try:
        res = compute_prediction_accuracy_metrics(
            observed_conc=list(req.observed_conc_mg_per_L),
            predicted_conc=list(req.predicted_conc_mg_per_L),
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return AccuracyMetricsResponse(**res)
