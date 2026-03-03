import re
from decimal import Decimal
from datetime import datetime
from typing import Dict, Tuple, List, Any, Optional

import requests
from sqlmodel import Session, select

from .models import Patient, Medication, MedicationTherapeuticWindowReview, Simulation
from .pk_scoring import (
    TherapeuticTargets,
    evaluate_therapeutic_window as score_therapeutic_window,
)

DEFAULT_HTTP_TIMEOUT = 8
USER_AGENT = "Capstone-Crew-Pharmaco/1.0 (+https://github.com/Whit3KD35/Capstone-Crew)"
SOURCE_WEIGHTS = {
    "dailymed": 3.0,
    "openfda": 2.5,
    "pubchem": 2.0,
}


# Network utilities
def _safe_get(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_HTTP_TIMEOUT,
):
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def list_supported_tdm_drugs(session: Session) -> list[dict[str, Any]]:
    rows = session.exec(
        select(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.status == "approved",
            MedicationTherapeuticWindowReview.source == "tdm-supported-db-seed",
        )
    ).all()
    out: list[dict[str, Any]] = []
    for row in rows:
        med = session.get(Medication, row.medication_id)
        if med is None:
            continue
        low = _dec_to_float(row.lower_mg_l)
        high = _dec_to_float(row.upper_mg_l)
        if low is None or high is None or high <= low:
            continue
        out.append(
            {
                "drug_name": med.name,
                "lower_mg_l": low,
                "upper_mg_l": high,
                "basis": row.reviewer_notes,
            }
        )
    return sorted(out, key=lambda x: x["drug_name"])


def _dec_to_float(x: Optional[Decimal | float | int]) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, Decimal):
        return float(x)
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _float_to_dec(x: Optional[float]) -> Optional[Decimal]:
    return Decimal(str(x)) if x is not None else None


def _estimate_active_moiety_fraction(med_name: str) -> float:
    name = (med_name or "").strip().lower()
    # Lithium carbonate is ~18.8% elemental lithium by mass.
    if "lithium carbonate" in name:
        return 0.188
    return 1.0


def _estimate_input_dose_for_target_window(
    drug_params: Dict[str, Optional[float]],
    interval_hr: float,
    active_fraction: float,
    target_low_mg_l: float,
    target_high_mg_l: float,
) -> Optional[float]:
    cl = drug_params.get("clearance_L_per_hr")
    f = drug_params.get("bioavailability")
    if cl is None or cl <= 0 or interval_hr <= 0:
        return None
    if active_fraction <= 0:
        return None
    if f is None or f <= 0:
        f = 1.0
    target_mid = (target_low_mg_l + target_high_mg_l) / 2.0
    modeled_dose = target_mid * cl * interval_hr / f
    if modeled_dose <= 0:
        return None
    return modeled_dose / active_fraction


def _recommend_regimens_for_window(
    drug_params: Dict[str, Optional[float]],
    active_fraction: float,
    current_input_dose_mg: float,
    current_interval_hr: float,
    num_doses: int,
    absorption_rate_hr: Optional[float],
    body_weight_kg: Optional[float],
    dt_hr: float,
    tw_low: float,
    tw_high: float,
    tw_targets: TherapeuticTargets,
    goal_pct_within: float = 96.0,
) -> list[Dict[str, Any]]:
    if current_input_dose_mg <= 0 or current_interval_hr <= 0:
        return []

    interval_candidates = sorted(
        {
            round(max(4.0, current_interval_hr * 0.5), 2),
            round(current_interval_hr, 2),
            round(min(48.0, current_interval_hr * 1.5), 2),
            10.0,
            16.0,
            8.0,
            12.0,
            24.0,
        }
    )
    dose_count_candidates = sorted(
        {
            max(2, int(num_doses)),
            max(2, int(round(num_doses * 0.5))),
            min(24, max(2, int(round(num_doses * 1.5)))),
            8,
            12,
            24,
        }
    )

    dose_candidates = sorted(
        {
            round(max(25.0, current_input_dose_mg * 0.5), 1),
            round(current_input_dose_mg * 0.75, 1),
            round(current_input_dose_mg, 1),
            round(current_input_dose_mg * 1.25, 1),
            round(current_input_dose_mg * 1.5, 1),
        }
    )

    candidates: list[Dict[str, Any]] = []
    for interval in interval_candidates:
        for n_doses in dose_count_candidates:
            for input_dose in dose_candidates:
                modeled_dose = input_dose * active_fraction
                try:
                    times, conc = predict_concentration_timecourse(
                        drug_params=drug_params,
                        dosing_mg=modeled_dose,
                        dosing_interval_hr=interval,
                        num_doses=n_doses,
                        absorption_rate_hr=absorption_rate_hr,
                        body_weight_kg=body_weight_kg,
                        dt_hr=dt_hr,
                    )
                    eval_res = evaluate_therapeutic_window(
                        times,
                        conc,
                        tw_low,
                        tw_high,
                        t_start_hr=0.0,
                        t_end_hr=interval * n_doses,
                        targets=tw_targets,
                    )
                except Exception:
                    continue
                candidates.append(
                    {
                        "dose_mg": input_dose,
                        "interval_hr": interval,
                        "num_doses": n_doses,
                        "pct_within": float(eval_res["pct_within"]),
                        "pct_below": float(eval_res["pct_below"]),
                        "pct_above": float(eval_res["pct_above"]),
                        "risk": str(eval_res["ade_risk_level"]),
                        "meets_goal_96pct": float(eval_res["pct_within"]) >= goal_pct_within,
                    }
                )

    # Rank by highest within-target %, then lower high-risk exposure, then lower low-risk exposure.
    ranked = sorted(
        candidates,
        key=lambda x: (
            x["meets_goal_96pct"],
            x["pct_within"],
            -x["pct_above"],
            -x["pct_below"],
        ),
        reverse=True,
    )
    return ranked[:5]


def _convert_concentration_to_mg_per_l(
    value: float,
    unit: str,
    drug_name: str,
) -> Optional[float]:
    u = (unit or "").strip().lower().replace(" ", "")
    if u in ("mg/l", "mgperliter", "mgperlitre"):
        return value
    if u in ("mcg/ml", "ug/ml"):
        return value
    if u == "ng/ml":
        return value / 1000.0
    if u == "mg/dl":
        return value * 10.0
    if u == "meq/l":
        # Only safe conversion implemented for lithium in current scope.
        if "lithium" in (drug_name or "").strip().lower():
            return value * 6.94
    return None


def _extract_therapeutic_window_from_raw(
    raw: str,
    drug_name: str,
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    if not raw:
        return None, None, None

    patterns = [
        r"(therapeutic(?:\s+serum)?\s+(?:range|window)|target(?:\s+serum)?\s+concentration|therapeutic levels?)"
        r"[^0-9]{0,80}([0-9]+(?:\.[0-9]+)?)\s*(?:-|to|–)\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(mg/L|mcg/mL|ug/mL|ng/mL|mg/dL|mEq/L)",
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:-|to|–)\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(mg/L|mcg/mL|ug/mL|ng/mL|mg/dL|mEq/L)[^.\n\r]{0,80}"
        r"(therapeutic(?:\s+serum)?\s+(?:range|window)|target(?:\s+serum)?\s+concentration|therapeutic levels?)",
        r"(serum|plasma)?\s*concentrations?[^0-9]{0,80}(?:between|of)?\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*(?:-|to|–|and)\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(mg/L|mcg/mL|ug/mL|ng/mL|mg/dL|mEq/L)",
    ]

    for pat in patterns:
        m = re.search(pat, raw, re.I)
        if not m:
            continue
        groups = m.groups()
        # pattern 1: keyword, low, high, unit
        # pattern 2: low, high, unit, keyword
        if len(groups) >= 4 and groups[0] and re.search(r"[a-zA-Z]", groups[0]):
            low_s, high_s, unit = groups[1], groups[2], groups[3]
        elif len(groups) >= 4 and groups[1] and re.match(r"[0-9]", groups[1]):
            low_s, high_s, unit = groups[1], groups[2], groups[3]
        else:
            low_s, high_s, unit = groups[0], groups[1], groups[2]
        try:
            low = float(low_s)
            high = float(high_s)
        except Exception:
            continue
        if high <= low or low < 0:
            continue
        low_mg_l = _convert_concentration_to_mg_per_l(low, unit, drug_name)
        high_mg_l = _convert_concentration_to_mg_per_l(high, unit, drug_name)
        if low_mg_l is None or high_mg_l is None or high_mg_l <= low_mg_l:
            continue
        return low_mg_l, high_mg_l, unit
    return None, None, None


def _propose_therapeutic_window_by_name(
    med_name: str,
    fetched_pk: Optional[Dict[str, Any]] = None,
) -> tuple[Optional[float], Optional[float], str, float]:
    if fetched_pk is not None:
        low = fetched_pk.get("therapeutic_window_lower_mg_l")
        high = fetched_pk.get("therapeutic_window_upper_mg_l")
        try:
            low_f = float(low) if low is not None else None
            high_f = float(high) if high is not None else None
        except Exception:
            low_f, high_f = None, None
        if low_f is not None and high_f is not None and high_f > low_f >= 0:
            used = 1
            lower_meta = fetched_pk.get("consensus", {}).get("therapeutic_window_lower_mg_l", {})
            if isinstance(lower_meta, dict):
                used = int(lower_meta.get("used_candidates", 1) or 1)
            conf = 70.0 + min(25.0, (used - 1) * 10.0)
            return low_f, high_f, "scraped-consensus", conf

    return None, None, "none", 0.0


def build_window_review_preview(
    session: Session,
    med_name: str,
    med: Medication | None = None,
    fetched_pk: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row: MedicationTherapeuticWindowReview | None = None
    if med is not None:
        row = session.exec(
            select(MedicationTherapeuticWindowReview).where(
                MedicationTherapeuticWindowReview.medication_id == med.id
            )
        ).first()
    else:
        by_name = session.exec(select(Medication).where(Medication.name == med_name)).first()
        if by_name is not None:
            row = session.exec(
                select(MedicationTherapeuticWindowReview).where(
                    MedicationTherapeuticWindowReview.medication_id == by_name.id
                )
            ).first()

    if row is not None:
        return {
            "status": row.status,
            "lower_mg_l": _dec_to_float(row.lower_mg_l),
            "upper_mg_l": _dec_to_float(row.upper_mg_l),
            "source": row.source,
            "confidence_pct": _dec_to_float(row.confidence_pct),
            "reviewer_notes": row.reviewer_notes,
        }

    low, high, source, confidence = _propose_therapeutic_window_by_name(med_name, fetched_pk=fetched_pk)
    if low is not None and high is not None and high > low:
        return {
            "status": "proposed",
            "lower_mg_l": low,
            "upper_mg_l": high,
            "source": source,
            "confidence_pct": confidence,
            "reviewer_notes": None,
        }
    return {
        "status": "manual_required",
        "lower_mg_l": None,
        "upper_mg_l": None,
        "source": source,
        "confidence_pct": confidence,
        "reviewer_notes": None,
    }


def upsert_window_review_proposal(
    session: Session,
    med: Medication,
    fetched_pk: Optional[Dict[str, Any]] = None,
) -> MedicationTherapeuticWindowReview:
    existing = session.exec(
        select(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.medication_id == med.id
        )
    ).first()

    approved = (
        existing is not None
        and existing.status == "approved"
        and existing.lower_mg_l is not None
        and existing.upper_mg_l is not None
    )
    if approved:
        return existing

    low, high, source, confidence = _propose_therapeutic_window_by_name(
        med.name,
        fetched_pk=fetched_pk,
    )

    if existing is None:
        existing = MedicationTherapeuticWindowReview(medication_id=med.id)

    if low is not None and high is not None and high > low:
        existing.lower_mg_l = _float_to_dec(low)
        existing.upper_mg_l = _float_to_dec(high)
        existing.source = source
        existing.confidence_pct = _float_to_dec(confidence)
        existing.status = "proposed"
    else:
        existing.status = "manual_required"
        existing.source = source
        existing.confidence_pct = _float_to_dec(confidence)
        existing.lower_mg_l = None
        existing.upper_mg_l = None

    existing.updated_at = datetime.now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def resolve_therapeutic_window_for_medication(
    session: Session,
    med: Medication,
) -> tuple[float, float, TherapeuticTargets, str]:
    review = session.exec(
        select(MedicationTherapeuticWindowReview).where(
            MedicationTherapeuticWindowReview.medication_id == med.id
        )
    ).first()
    if (
        review is not None
        and review.status == "approved"
        and review.lower_mg_l is not None
        and review.upper_mg_l is not None
    ):
        low = _dec_to_float(review.lower_mg_l)
        high = _dec_to_float(review.upper_mg_l)
        if low is not None and high is not None and low >= 0 and high > low:
            return low, high, _resolve_targets_for_medication(med), "review-approved"

    low = _dec_to_float(med.therapeutic_window_lower_mg_l)
    high = _dec_to_float(med.therapeutic_window_upper_mg_l)
    if low is not None and high is not None and low >= 0 and high > low:
        return low, high, _resolve_targets_for_medication(med), "medication-db"

    # Fallback when drug-specific concentration windows are not configured.
    return 1.0, 10.0, TherapeuticTargets(), "global-default"


# PK text parsing
def _extract_half_life_hours(raw: str) -> Optional[float]:
    if not raw:
        return None

    text = raw

    m = re.search(
        r"effective\s+half[ -]?life[^.\n\r]*?mean of(?: about)?\s*([0-9]+(?:\.[0-9]+)?)\s*hours",
        text,
        re.I,
    )
    if m:
        return float(m.group(1))

    m = re.search(
        r"effective\s+half[ -]?life[^.\n\r]*?ranges?\s+from\s+([0-9]+(?:\.[0-9]+)?)\s*"
        r"to\s*([0-9]+(?:\.[0-9]+)?)\s*hours",
        text,
        re.I,
    )
    if m:
        low = float(m.group(1))
        high = float(m.group(2))
        return (low + high) / 2.0

    m = re.search(
        r"s-?warfarin[^.\n\r]*?([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*hours",
        text,
        re.I,
    )
    if m:
        low = float(m.group(1))
        high = float(m.group(2))
        return (low + high) / 2.0

    m = re.search(
        r"half[ -]?life[^0-9\n\r:]*?([0-9]+(?:\.[0-9]+)?)\s*"
        r"(h|hr|hrs|hour|hours|d|day|days|wk|wks|week|weeks)",
        text,
        re.I,
    )
    if m:
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("h"):
            return val
        elif unit.startswith("d"):
            return val * 24.0
        elif unit.startswith("w"):
            return val * 24.0 * 7.0

    return None


def _convert_clearance_to_l_per_hr(
    val: float, unit: str, reference_weight_kg: float = 70.0
) -> Optional[float]:
    unit_clean = unit.lower().replace(" ", "")
    if "ml/min/kg" in unit_clean:
        return val * reference_weight_kg / 1000.0 * 60.0
    if "ml/min" in unit_clean:
        return val / 1000.0 * 60.0
    if "l/h/kg" in unit_clean or "l/hr/kg" in unit_clean:
        return val * reference_weight_kg
    if "l/h/70kg" in unit_clean or "l/hr/70kg" in unit_clean:
        return val
    if "l/h" in unit_clean or "l/hr" in unit_clean or "lperh" in unit_clean:
        return val
    return None


def _parse_pk_fields_from_raw(
    raw: str,
    reference_weight_kg: float = 70.0,
    drug_name: str = "",
) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
        "therapeutic_window_lower_mg_l": None,
        "therapeutic_window_upper_mg_l": None,
        "therapeutic_window_raw_unit": None,
        "clearance_raw_value": None,
        "clearance_raw_unit": None,
        "Vd_raw_value": None,
        "Vd_raw_unit": None,
    }
    if not raw:
        return parsed

    half_val = _extract_half_life_hours(raw)
    if half_val is not None:
        parsed["half_life_hr"] = half_val

    m_cl = re.search(
        r"clearance[^0-9\n\r:]*?([0-9]+(?:\.[0-9]+)?)\s*"
        r"(mL\s*/\s*min\s*/\s*kg|mL\s*/\s*min|L\s*/\s*h\s*/\s*kg|L\s*/\s*h|L\s*/\s*hr|L\s*/\s*h\s*/\s*70\s*kg|L\s*/\s*hr\s*/\s*70\s*kg|L\s*per\s*h)",
        raw,
        re.I,
    )
    if m_cl:
        raw_val = float(m_cl.group(1))
        raw_unit = m_cl.group(2).strip()
        parsed["clearance_raw_value"] = raw_val
        parsed["clearance_raw_unit"] = raw_unit
        parsed["clearance_L_per_hr"] = _convert_clearance_to_l_per_hr(
            raw_val, raw_unit, reference_weight_kg
        )
    else:
        m_cl2 = re.search(
            r"([0-9]+(?:\.[0-9]+)?)\s*"
            r"(mL\s*/\s*min\s*/\s*kg|mL\s*/\s*min|L\s*/\s*h\s*/\s*kg|L\s*/\s*h|L\s*/\s*hr)",
            raw,
            re.I,
        )
        if m_cl2:
            raw_val = float(m_cl2.group(1))
            raw_unit = m_cl2.group(2).strip()
            parsed["clearance_raw_value"] = raw_val
            parsed["clearance_raw_unit"] = raw_unit
            parsed["clearance_L_per_hr"] = _convert_clearance_to_l_per_hr(
                raw_val, raw_unit, reference_weight_kg
            )

    m_vd = re.search(
        r"(volume of distribution|Vd)[^0-9\n\r:]*?"
        r"([0-9]+(?:\.[0-9]+)?)\s*(L\s*/\s*kg|L/kg|L|liters?)",
        raw,
        re.I,
    )
    if m_vd:
        raw_val = float(m_vd.group(2))
        raw_unit = m_vd.group(3).strip()
        parsed["Vd_raw_value"] = raw_val
        parsed["Vd_raw_unit"] = raw_unit
        unit_clean = raw_unit.lower().replace(" ", "")
        parsed["Vd_L"] = raw_val * reference_weight_kg if "l/kg" in unit_clean else raw_val

    m_f = re.search(
        r"(bioavailability|absolute bioavailability)[^0-9%\n\r:]*?"
        r"([0-9]{1,3}(?:\.[0-9]+)?)\s*%?",
        raw,
        re.I,
    )
    if not m_f:
        m_f = re.search(
            r"([0-9]{1,3}(?:\.[0-9]+)?)\s*%[^.\n\r]*bioavailability",
            raw,
            re.I,
        )
    if m_f:
        val = float(m_f.group(2)) if (m_f.lastindex and m_f.lastindex >= 2) else float(m_f.group(1))
        parsed["bioavailability"] = val / 100.0 if val > 1 else val
    else:
        lower = raw.lower()
        if "completely absorbed" in lower or "almost completely absorbed" in lower:
            parsed["bioavailability"] = 1.0
        elif "high oral bioavailability" in lower:
            parsed["bioavailability"] = 0.9

    tw_low, tw_high, tw_unit = _extract_therapeutic_window_from_raw(raw, drug_name=drug_name)
    if tw_low is not None and tw_high is not None and tw_high > tw_low:
        parsed["therapeutic_window_lower_mg_l"] = tw_low
        parsed["therapeutic_window_upper_mg_l"] = tw_high
        parsed["therapeutic_window_raw_unit"] = tw_unit

    return parsed


def _cluster_consensus(
    field_name: str,
    candidates: List[Dict[str, Any]],
) -> tuple[Optional[float], Dict[str, Any]]:
    if not candidates:
        return None, {
            "field": field_name,
            "total_candidates": 0,
            "used_candidates": 0,
            "sources_used": [],
        }

    if len(candidates) == 1:
        only = candidates[0]
        return float(only["value"]), {
            "field": field_name,
            "total_candidates": 1,
            "used_candidates": 1,
            "sources_used": [only["source"]],
            "method": "single-source",
        }

    tolerance = 0.2
    if field_name == "bioavailability":
        tolerance = 0.15

    clusters: List[Dict[str, Any]] = []

    for cand in sorted(candidates, key=lambda x: x["value"]):
        assigned = False
        for cluster in clusters:
            center = cluster["center"]
            if field_name == "bioavailability":
                close = abs(cand["value"] - center) <= tolerance
            else:
                denom = max(abs(center), 1e-9)
                close = abs(cand["value"] - center) / denom <= tolerance

            if close:
                cluster["items"].append(cand)
                vals = sorted([x["value"] for x in cluster["items"]])
                cluster["center"] = vals[len(vals) // 2]
                assigned = True
                break

        if not assigned:
            clusters.append({"center": cand["value"], "items": [cand]})

    def _cluster_score(cluster: Dict[str, Any]) -> tuple[float, float]:
        count = float(len(cluster["items"]))
        weight_sum = sum(float(x["weight"]) for x in cluster["items"])
        return (count, weight_sum)

    best = max(clusters, key=_cluster_score)
    used = best["items"]
    total_w = sum(float(x["weight"]) for x in used)
    consensus = (
        sum(float(x["value"]) * float(x["weight"]) for x in used) / total_w
        if total_w > 0
        else sum(float(x["value"]) for x in used) / len(used)
    )

    values = [float(x["value"]) for x in used]
    spread = max(values) - min(values) if values else 0.0
    mean_abs = max(abs(consensus), 1e-9)
    spread_pct = (spread / mean_abs) * 100.0

    if field_name == "bioavailability":
        consensus = max(0.0, min(1.0, consensus))

    return consensus, {
        "field": field_name,
        "total_candidates": len(candidates),
        "used_candidates": len(used),
        "sources_used": sorted(list({x["source"] for x in used})),
        "method": "clustered-weighted-mean",
        "spread_pct": spread_pct,
    }


# Patient utils
def compute_creatinine_clearance(
    age: float, weight_kg: float, serum_creatinine_mg_dl: float, sex: str
) -> float:
    sex_u = (sex or "").strip().upper()
    if serum_creatinine_mg_dl <= 0:
        raise ValueError("serum_creatinine_mg_dl must be > 0")
    crcl = ((140.0 - age) * weight_kg) / (72.0 * serum_creatinine_mg_dl)
    if sex_u in ("F", "FEMALE"):
        crcl *= 0.85
    return crcl


def ensure_patient_crcl(session: Session, patient: Patient) -> None:
    if patient.creatinine_clearance_ml_min is not None:
        return
    if patient.age is None or patient.sex is None or patient.serum_creatinine_mg_dl is None:
        return
    wkg = _dec_to_float(patient.weight_kg)
    legacy_weight = getattr(patient, "weight", None)
    if wkg is None and legacy_weight is not None:
        wkg = float(legacy_weight)
    if wkg is None:
        return
    crcl = compute_creatinine_clearance(
        age=float(patient.age),
        weight_kg=wkg,
        serum_creatinine_mg_dl=float(patient.serum_creatinine_mg_dl),
        sex=str(patient.sex),
    )
    patient.creatinine_clearance_ml_min = _float_to_dec(crcl)
    session.add(patient)
    session.commit()


# Drug fetching
def fetch_from_pubchem(drug_name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "raw": None,
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
        "therapeutic_window_lower_mg_l": None,
        "therapeutic_window_upper_mg_l": None,
        "therapeutic_window_raw_unit": None,
        "clearance_raw_value": None,
        "clearance_raw_unit": None,
        "Vd_raw_value": None,
        "Vd_raw_unit": None,
    }

    url_cid = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{requests.utils.requote_uri(drug_name)}/cids/JSON"
    )
    r1 = _safe_get(url_cid)
    if not r1:
        return out

    try:
        cids = r1.json().get("IdentifierList", {}).get("CID", [])
        if not cids:
            return out
        cid = cids[0]
    except Exception:
        return out

    url_view = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
    r2 = _safe_get(url_view)
    if not r2:
        return out

    try:
        j = r2.json()

        def collect_strings(node, acc):
            if isinstance(node, dict):
                swm = node.get("StringWithMarkup")
                if isinstance(swm, list):
                    for v in swm:
                        s = v.get("String")
                        if isinstance(s, str) and s:
                            acc.append(s)
                for v in node.values():
                    collect_strings(v, acc)
            elif isinstance(node, list):
                for v in node:
                    collect_strings(v, acc)

        texts: list = []
        collect_strings(j, texts)
        raw = "\n".join(texts) if texts else None
        out["raw"] = raw

        if not raw:
            return out

        parsed = _parse_pk_fields_from_raw(raw, drug_name=drug_name)
        for k, v in parsed.items():
            if v is not None:
                out[k] = v

    except Exception:
        pass

    return out


def fetch_from_dailymed(drug_name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "raw": None,
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
        "therapeutic_window_lower_mg_l": None,
        "therapeutic_window_upper_mg_l": None,
        "therapeutic_window_raw_unit": None,
        "clearance_raw_value": None,
        "clearance_raw_unit": None,
        "Vd_raw_value": None,
        "Vd_raw_unit": None,
    }

    search_url = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
    r = _safe_get(search_url, params={"drug_label_name": drug_name})
    if not r:
        r = _safe_get(search_url, params={"search": drug_name})
        if not r:
            return out

    try:
        items = r.json().get("data", [])
        if not items:
            return out

        setid = items[0].get("setid")
        if not setid:
            return out

        spl_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.json"
        r2 = _safe_get(spl_url, headers={"Accept": "application/json"})
        if not r2:
            return out

        label = r2.json().get("data", {})
        sections = label.get("sections", []) or []

        texts: list = []
        for sec in sections:
            title = (sec.get("title") or "").lower()
            if (
                "pharmacokinetics" in title
                or "clinical pharmacology" in title
                or "dosage and administration" in title
                or "therapeutic drug monitoring" in title
                or "warnings and precautions" in title
            ):
                txt = sec.get("text") or ""
                if txt:
                    texts.append(txt)

        raw = "\n".join(texts) if texts else None
        out["raw"] = raw

        if not raw:
            return out

        parsed = _parse_pk_fields_from_raw(raw, drug_name=drug_name)
        for k, v in parsed.items():
            if v is not None:
                out[k] = v

    except Exception:
        pass

    return out


def fetch_from_openfda(drug_name: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "raw": None,
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
        "therapeutic_window_lower_mg_l": None,
        "therapeutic_window_upper_mg_l": None,
        "therapeutic_window_raw_unit": None,
        "clearance_raw_value": None,
        "clearance_raw_unit": None,
        "Vd_raw_value": None,
        "Vd_raw_unit": None,
    }

    search_terms = [
        f'openfda.brand_name:"{drug_name}"',
        f'openfda.generic_name:"{drug_name}"',
        f'openfda.substance_name:"{drug_name}"',
    ]

    base_url = "https://api.fda.gov/drug/label.json"
    resp = None
    for q in search_terms:
        resp = _safe_get(base_url, params={"search": q, "limit": 1})
        if resp:
            break
    if not resp:
        return out

    try:
        results = resp.json().get("results", [])
        if not results:
            return out
        label = results[0]
        texts: List[str] = []
        for key in (
            "clinical_pharmacology",
            "pharmacokinetics",
            "description",
            "mechanism_of_action",
            "dosage_and_administration",
            "warnings",
            "warnings_and_cautions",
            "warnings_and_precautions",
            "indications_and_usage",
        ):
            val = label.get(key)
            if isinstance(val, list):
                texts.extend([str(x) for x in val if x])
            elif isinstance(val, str):
                texts.append(val)

        raw = "\n".join(texts) if texts else None
        out["raw"] = raw
        if not raw:
            return out

        parsed = _parse_pk_fields_from_raw(raw, drug_name=drug_name)
        for k, v in parsed.items():
            if v is not None:
                out[k] = v
    except Exception:
        pass

    return out


def fetch_drug_pharmacokinetics(drug_name: str) -> Dict[str, Any]:
    pk: Dict[str, Any] = {
        "half_life_hr": None,
        "clearance_L_per_hr": None,
        "Vd_L": None,
        "bioavailability": None,
        "therapeutic_window_lower_mg_l": None,
        "therapeutic_window_upper_mg_l": None,
        "clearance_raw_value": None,
        "clearance_raw_unit": None,
        "Vd_raw_value": None,
        "Vd_raw_unit": None,
        "sources": {},
        "consensus": {},
    }

    source_values: Dict[str, Dict[str, Any]] = {}

    try:
        dm = fetch_from_dailymed(drug_name)
        pk["sources"]["dailymed"] = dm.get("raw")
        source_values["dailymed"] = dm
    except Exception:
        pass

    try:
        ofda = fetch_from_openfda(drug_name)
        pk["sources"]["openfda"] = ofda.get("raw")
        source_values["openfda"] = ofda
    except Exception:
        pass

    try:
        pc = fetch_from_pubchem(drug_name)
        pk["sources"]["pubchem"] = pc.get("raw")
        source_values["pubchem"] = pc
    except Exception:
        pass

    for field in (
        "half_life_hr",
        "clearance_L_per_hr",
        "Vd_L",
        "bioavailability",
        "therapeutic_window_lower_mg_l",
        "therapeutic_window_upper_mg_l",
    ):
        candidates: List[Dict[str, Any]] = []
        for source_name, values in source_values.items():
            value = values.get(field)
            if value is None:
                continue
            try:
                val_f = float(value)
            except (TypeError, ValueError):
                continue
            candidates.append(
                {
                    "source": source_name,
                    "value": val_f,
                    "weight": SOURCE_WEIGHTS.get(source_name, 1.0),
                }
            )
        consensus_value, consensus_meta = _cluster_consensus(field, candidates)
        pk["consensus"][field] = consensus_meta
        pk[field] = consensus_value

    clearance_target = pk.get("clearance_L_per_hr")
    if clearance_target is not None:
        best = None
        for source_name, values in source_values.items():
            raw_val = values.get("clearance_raw_value")
            raw_unit = values.get("clearance_raw_unit")
            converted = values.get("clearance_L_per_hr")
            if raw_val is None or raw_unit is None or converted is None:
                continue
            diff = abs(float(converted) - float(clearance_target))
            if best is None or diff < best["diff"]:
                best = {
                    "diff": diff,
                    "raw_value": raw_val,
                    "raw_unit": raw_unit,
                }
        if best is not None:
            pk["clearance_raw_value"] = best["raw_value"]
            pk["clearance_raw_unit"] = best["raw_unit"]

    vd_target = pk.get("Vd_L")
    if vd_target is not None:
        best = None
        for source_name, values in source_values.items():
            raw_val = values.get("Vd_raw_value")
            raw_unit = values.get("Vd_raw_unit")
            converted = values.get("Vd_L")
            if raw_val is None or raw_unit is None or converted is None:
                continue
            diff = abs(float(converted) - float(vd_target))
            if best is None or diff < best["diff"]:
                best = {
                    "diff": diff,
                    "raw_value": raw_val,
                    "raw_unit": raw_unit,
                }
        if best is not None:
            pk["Vd_raw_value"] = best["raw_value"]
            pk["Vd_raw_unit"] = best["raw_unit"]

    # half-life from CL + Vd
    try:
        if (
            pk["half_life_hr"] is None
            and pk["Vd_L"] is not None
            and pk["clearance_L_per_hr"] is not None
        ):
            pk["half_life_hr"] = 0.693 * (pk["Vd_L"] / pk["clearance_L_per_hr"])
    except Exception:
        pass

    try:
        tw_low = pk.get("therapeutic_window_lower_mg_l")
        tw_high = pk.get("therapeutic_window_upper_mg_l")
        if tw_low is not None and tw_high is not None and float(tw_high) <= float(tw_low):
            pk["therapeutic_window_lower_mg_l"] = None
            pk["therapeutic_window_upper_mg_l"] = None
    except Exception:
        pk["therapeutic_window_lower_mg_l"] = None
        pk["therapeutic_window_upper_mg_l"] = None

    return pk


# Simulation core
def predict_concentration_timecourse(
    drug_params: Dict[str, Optional[float]],
    dosing_mg: float,
    dosing_interval_hr: float,
    num_doses: int,
    absorption_rate_hr: Optional[float] = None,
    body_weight_kg: Optional[float] = None,
    t_end_hr: Optional[float] = None,
    dt_hr: float = 0.1,
) -> Tuple[List[float], List[float]]:
    half = drug_params.get("half_life_hr")
    CL = drug_params.get("clearance_L_per_hr")
    Vd = drug_params.get("Vd_L")
    F = drug_params.get("bioavailability")

    # bioavailability (no guessing for non-IV)
    if F is None:
        if absorption_rate_hr is not None:
            raise ValueError(
                "bioavailability_f is required for non-IV dosing (absorption_rate_hr set)"
            )
        F = 1.0

    # CL from half-life + Vd
    if CL is None and half and Vd:
        CL = 0.693 * Vd / half

    if CL is None or Vd is None:
        raise ValueError(
            "Insufficient PK parameters: need Vd_L and clearance_L_per_hr "
            "(or half_life_hr plus one of them)"
        )

    kel = CL / Vd
    if half is None:
        half = 0.693 / kel

    # simulate through dosing + ~5 half-lives
    if t_end_hr is None:
        t_end_hr = (num_doses * dosing_interval_hr) + (5.0 * half)

    times: List[float] = []
    conc: List[float] = []

    dose_times = [i * dosing_interval_hr for i in range(num_doses)]
    A_central_mg = 0.0
    A_gut_mg = 0.0
    ka = absorption_rate_hr if absorption_rate_hr is not None else None

    t = 0.0
    while t <= t_end_hr + 1e-9:
        # dosing
        for td in dose_times:
            if abs(t - td) < dt_hr / 2.0:
                if ka is not None:
                    A_gut_mg += dosing_mg
                else:
                    A_central_mg += dosing_mg * F

        # absorption
        if ka is not None:
            absorbed = ka * A_gut_mg * dt_hr
            if absorbed > A_gut_mg:
                absorbed = A_gut_mg
            A_gut_mg -= absorbed
            A_central_mg += absorbed * F

        # elimination
        elim = (CL / Vd) * A_central_mg * dt_hr
        if elim > A_central_mg:
            elim = A_central_mg
        A_central_mg -= elim

        C = (A_central_mg / Vd) if Vd > 0 else 0.0
        times.append(round(t, 6))
        conc.append(C)
        t += dt_hr

    return times, conc


def evaluate_therapeutic_window(
    times: List[float],
    conc: List[float],
    therapeutic_min_mg_per_L: float,
    therapeutic_max_mg_per_L: float,
    t_start_hr: Optional[float] = None,
    t_end_hr: Optional[float] = None,
    targets: Optional[TherapeuticTargets] = None,
) -> Dict[str, Any]:
    chosen_targets = targets or TherapeuticTargets()
    return score_therapeutic_window(
        times_hr=times,
        conc_mg_per_L=conc,
        lower_mg_per_L=therapeutic_min_mg_per_L,
        upper_mg_per_L=therapeutic_max_mg_per_L,
        t_start_hr=t_start_hr,
        t_end_hr=t_end_hr,
        targets=chosen_targets,
    )


def compute_prediction_accuracy_metrics(
    observed_conc: List[float],
    predicted_conc: List[float],
) -> Dict[str, float]:
    if not observed_conc or not predicted_conc or len(observed_conc) != len(predicted_conc):
        raise ValueError("observed_conc and predicted_conc must be same non-zero length")

    n = len(observed_conc)
    abs_errors: List[float] = []
    sq_errors: List[float] = []
    rel_errors_pct: List[float] = []
    ape_pct: List[float] = []
    within_20 = 0
    within_30 = 0

    for obs, pred in zip(observed_conc, predicted_conc):
        err = pred - obs
        abs_err = abs(err)
        abs_errors.append(abs_err)
        sq_errors.append(err * err)

        if obs != 0:
            rel_pct = (err / obs) * 100.0
            abs_rel_pct = abs(rel_pct)
            rel_errors_pct.append(rel_pct)
            ape_pct.append(abs_rel_pct)
            if abs_rel_pct <= 20.0:
                within_20 += 1
            if abs_rel_pct <= 30.0:
                within_30 += 1

    nonzero_n = len(ape_pct)
    mape = (sum(ape_pct) / nonzero_n) if nonzero_n else 0.0
    mpe = (sum(rel_errors_pct) / nonzero_n) if nonzero_n else 0.0
    mae = sum(abs_errors) / n
    rmse = (sum(sq_errors) / n) ** 0.5
    p20 = (within_20 / nonzero_n * 100.0) if nonzero_n else 0.0
    p30 = (within_30 / nonzero_n * 100.0) if nonzero_n else 0.0

    return {
        "n_total": float(n),
        "n_nonzero_observed": float(nonzero_n),
        "mae": mae,
        "rmse": rmse,
        "mpe_pct": mpe,
        "mape_pct": mape,
        "p20_pct": p20,
        "p30_pct": p30,
    }


def _resolve_targets_for_medication(med: Medication) -> TherapeuticTargets:
    return TherapeuticTargets()


# Building PK from DB
def _convert_clearance_from_raw(
    val: float, unit: str, weight_kg: Optional[float]
) -> Optional[float]:
    unit_clean = unit.lower().replace(" ", "")
    ref_weight = weight_kg if weight_kg is not None else 70.0
    if "ml/min/kg" in unit_clean:
        return val * ref_weight / 1000.0 * 60.0
    if "ml/min" in unit_clean:
        return val / 1000.0 * 60.0
    if "l/h/kg" in unit_clean or "l/hr/kg" in unit_clean:
        return val * ref_weight
    if "l/h" in unit_clean or "l/hr" in unit_clean or "lperh" in unit_clean:
        return val
    return None


def _convert_vd_from_raw(
    val: float, unit: str, weight_kg: Optional[float]
) -> Optional[float]:
    unit_clean = unit.lower().replace(" ", "")
    ref_weight = weight_kg if weight_kg is not None else 70.0
    if "l/kg" in unit_clean:
        return val * ref_weight
    return val


def build_drug_params_from_db(
    med: Medication, fallback_weight_kg: Optional[float] = None
) -> Dict[str, Optional[float]]:
    half = _dec_to_float(med.half_life_hr)
    f = _dec_to_float(med.bioavailability_f)

    cl: Optional[float] = None
    vd: Optional[float] = None

    if med.clearance_raw_value is not None and med.clearance_raw_unit:
        raw_cl_val = _dec_to_float(med.clearance_raw_value)
        if raw_cl_val is not None:
            cl = _convert_clearance_from_raw(raw_cl_val, med.clearance_raw_unit, fallback_weight_kg)

    if med.volume_of_distribution_raw_value is not None and med.volume_of_distribution_raw_unit:
        raw_vd_val = _dec_to_float(med.volume_of_distribution_raw_value)
        if raw_vd_val is not None:
            vd = _convert_vd_from_raw(
                raw_vd_val, med.volume_of_distribution_raw_unit, fallback_weight_kg
            )

    # CL from half-life + Vd
    if cl is None and half is not None and vd is not None:
        cl = 0.693 * vd / half

    return {
        "half_life_hr": half,
        "clearance_L_per_hr": cl,
        "Vd_L": vd,
        "bioavailability": f,
    }


def maybe_enrich_medication_from_sources(session: Session, med: Medication) -> None:
    params = build_drug_params_from_db(med)
    # already have Vd and (CL or half-life)
    if params["Vd_L"] is not None and (
        params["clearance_L_per_hr"] is not None or params["half_life_hr"] is not None
    ):
        return

    fetched = fetch_drug_pharmacokinetics(med.name)

    if med.half_life_hr is None and fetched.get("half_life_hr") is not None:
        med.half_life_hr = _float_to_dec(fetched["half_life_hr"])
    if med.bioavailability_f is None and fetched.get("bioavailability") is not None:
        med.bioavailability_f = _float_to_dec(fetched["bioavailability"])

    if med.clearance_raw_value is None and fetched.get("clearance_raw_value") is not None:
        med.clearance_raw_value = _float_to_dec(fetched["clearance_raw_value"])
    if med.clearance_raw_unit is None and fetched.get("clearance_raw_unit") is not None:
        med.clearance_raw_unit = fetched["clearance_raw_unit"]

    if med.volume_of_distribution_raw_value is None and fetched.get("Vd_raw_value") is not None:
        med.volume_of_distribution_raw_value = _float_to_dec(fetched["Vd_raw_value"])
    if med.volume_of_distribution_raw_unit is None and fetched.get("Vd_raw_unit") is not None:
        med.volume_of_distribution_raw_unit = fetched["Vd_raw_unit"]

    session.add(med)
    session.commit()


# Simulation storage
def simulate_and_store(
    session: Session,
    patient_id: str,
    medication_id: str,
    dose_mg: float,
    interval_hr: float,
    num_doses: int,
    absorption_rate_hr: Optional[float] = None,
    dt_hr: float = 0.1,
) -> Simulation:
    pat = session.exec(select(Patient).where(Patient.id == patient_id)).first()
    med = session.exec(select(Medication).where(Medication.id == medication_id)).first()
    if not pat or not med:
        raise ValueError("Patient or Medication not found")

    ensure_patient_crcl(session, pat)
    maybe_enrich_medication_from_sources(session, med)

    weight_kg = _dec_to_float(pat.weight_kg) or (
        float(getattr(pat, "weight")) if getattr(pat, "weight", None) is not None else None
    )
    drug_params = build_drug_params_from_db(med, fallback_weight_kg=weight_kg)

    half = drug_params["half_life_hr"]
    cl = drug_params["clearance_L_per_hr"]
    vd = drug_params["Vd_L"]

    missing_msgs: List[str] = []
    if vd is None:
        missing_msgs.append(
            "- Vd_L (volume_of_distribution_raw_value + volume_of_distribution_raw_unit)"
        )
    if cl is None and half is None:
        missing_msgs.append(
            "- clearance or half_life_hr "
            "(clearance_raw_value + clearance_raw_unit, or half_life_hr)"
        )

    if missing_msgs:
        raise ValueError(
            f"Missing PK parameters for medication '{med.name}'.\n"
            "Required fields:\n" + "\n".join(missing_msgs)
        )

    active_fraction = _estimate_active_moiety_fraction(med.name)
    modeled_dose_mg = dose_mg * active_fraction
    tw_low, tw_high, tw_targets, tw_source = resolve_therapeutic_window_for_medication(session, med)
    suggested_input_dose_mg = _estimate_input_dose_for_target_window(
        drug_params=drug_params,
        interval_hr=interval_hr,
        active_fraction=active_fraction,
        target_low_mg_l=tw_low,
        target_high_mg_l=tw_high,
    )
    recommended_regimens = _recommend_regimens_for_window(
        drug_params=drug_params,
        active_fraction=active_fraction,
        current_input_dose_mg=dose_mg,
        current_interval_hr=interval_hr,
        num_doses=num_doses,
        absorption_rate_hr=absorption_rate_hr,
        body_weight_kg=weight_kg,
        dt_hr=dt_hr,
        tw_low=tw_low,
        tw_high=tw_high,
        tw_targets=tw_targets,
        goal_pct_within=96.0,
    )

    times, conc = predict_concentration_timecourse(
        drug_params=drug_params,
        dosing_mg=modeled_dose_mg,
        dosing_interval_hr=interval_hr,
        num_doses=num_doses,
        absorption_rate_hr=absorption_rate_hr,
        body_weight_kg=weight_kg,
        dt_hr=dt_hr,
    )

    therapy_end = interval_hr * num_doses
    eval_res = evaluate_therapeutic_window(
        times,
        conc,
        tw_low,
        tw_high,
        t_start_hr=0.0,
        t_end_hr=therapy_end,
        targets=tw_targets,
    )

    cmax = max(conc) if conc else None
    cmin = min(conc) if conc else None
    auc = 0.0
    for i in range(len(times) - 1):
        dt = times[i + 1] - times[i]
        auc += 0.5 * (conc[i] + conc[i + 1]) * dt

    sim = Simulation(
        patient_id=pat.id,
        medication_id=med.id,
        dose_mg=_float_to_dec(dose_mg),
        interval_hr=_float_to_dec(interval_hr),
        duration_hr=_float_to_dec(times[-1] if times else 0.0),
        cmax_mg_l=_float_to_dec(cmax),
        cmin_mg_l=_float_to_dec(cmin),
        auc_mg_h_l=_float_to_dec(auc),
        flag_too_high=eval_res["pct_above"] > 5.0,
        flag_too_low=eval_res["pct_below"] > 20.0,
        sim_results={
            "times_hr": times,
            "conc_mg_per_L": conc,
            "therapeutic_eval": eval_res,
            "params_used": {
                **drug_params,
                "dose_input_mg": dose_mg,
                "dose_modeled_mg": modeled_dose_mg,
                "active_moiety_fraction": active_fraction,
                "therapeutic_window_source": tw_source,
                "therapeutic_window_lower_mg_l": tw_low,
                "therapeutic_window_upper_mg_l": tw_high,
                "suggested_input_dose_mg_for_mid_window": suggested_input_dose_mg,
                "recommended_regimens": recommended_regimens,
            },
        },
    )

    session.add(sim)
    session.commit()
    session.refresh(sim)
    return sim
