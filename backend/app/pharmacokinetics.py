import os
import re
from decimal import Decimal
from typing import Dict, Tuple, List, Any, Optional

import requests
from sqlmodel import Session, select

from .models import Patient, Medication, Simulation

DEFAULT_HTTP_TIMEOUT = 8
USER_AGENT = "Capstone-Crew-Pharmaco/1.0 (+https://github.com/Whit3KD35/Capstone-Crew)"

def _safe_get(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = DEFAULT_HTTP_TIMEOUT):
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None

def _extract_number_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", text.replace(",", ""))
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None

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


# patient utils
def compute_creatinine_clearance(age: float, weight_kg: float, serum_creatinine_mg_dl: float, sex: str) -> float:
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
    if wkg is None and patient.weight is not None:
        wkg = float(patient.weight)
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


# medication fetch + build parameters
def fetch_from_pubchem(drug_name: str) -> Dict[str, Any]:
    out = {"raw": None, "half_life_hr": None, "clearance_L_per_hr": None, "Vd_L": None, "bioavailability": None}

    url_cid = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{requests.utils.requote_uri(drug_name)}/cids/JSON"
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
        sections = j.get("Record", {}).get("Section", [])

        def find_sections(secs):
            acc = []
            for s in secs:
                if s.get("TOCHeading", "").lower().startswith("pharmacokinetics"):
                    acc.append(s)
                for cs in s.get("Section", []) or []:
                    acc.extend(find_sections([cs]))
            return acc

        pk_sections = find_sections(sections)
        texts = []
        for s in pk_sections:
            for info in s.get("Information", []) or []:
                for v in info.get("Value", {}).get("StringWithMarkup", []) or []:
                    texts.append(v.get("String", ""))
        raw = "\n".join(texts) if texts else None
        out["raw"] = raw

        if raw:
            m_half = re.search(r"half[ -]?life[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(h|hr|hours?)", raw, re.I)
            if m_half:
                out["half_life_hr"] = float(m_half.group(1))

            m_vd = re.search(r"(volume of distribution|Vd)[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(L|liters?)", raw, re.I)
            if m_vd:
                out["Vd_L"] = float(m_vd.group(2))

            m_cl = re.search(r"clearance[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(mL/min|mL\/min|L\/h|L/h|mL per min|L per h)", raw, re.I)
            if m_cl:
                val = float(m_cl.group(1))
                unit = m_cl.group(2).lower()
                out["clearance_L_per_hr"] = (val / 1000.0) * 60.0 if "ml" in unit else val

            m_f = re.search(r"(bioavailability|absolute bioavailability)[^0-9\n\r\:]*?([0-9]{1,3})\s*%?", raw, re.I)
            if m_f:
                val = float(m_f.group(2))
                out["bioavailability"] = val / 100.0 if val > 1 else val
    except Exception:
        pass

    return out

def fetch_from_dailymed(drug_name: str) -> Dict[str, Any]:
    out = {"raw": None, "half_life_hr": None, "clearance_L_per_hr": None, "Vd_L": None, "bioavailability": None}

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

        spl_url = f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
        r2 = _safe_get(spl_url, headers={"Accept": "application/xml"})
        if not r2:
            return out
        label = r2.json().get("data", {})
        sections = label.get("sections", []) or []

        texts = []
        for sec in sections:
            heading = (sec.get("title") or "").lower()
            if "pharmacokinetics" in heading:
                texts.append(sec.get("text", "") or "")
        raw = "\n".join(texts) if texts else None
        out["raw"] = raw

        if raw:
            m_half = re.search(r"half[ -]?life[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(h|hr|hours?)", raw, re.I)
            if m_half:
                out["half_life_hr"] = float(m_half.group(1))

            m_vd = re.search(r"(volume of distribution|Vd)[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(L|liters?)", raw, re.I)
            if m_vd:
                out["Vd_L"] = float(m_vd.group(2))

            m_cl = re.search(r"clearance[^0-9\n\r\:]*?([0-9]+(?:\.[0-9]+)?)\s*(mL/min|mL\/min|L\/h|L/h)", raw, re.I)
            if m_cl:
                val = float(m_cl.group(1))
                unit = m_cl.group(2).lower()
                out["clearance_L_per_hr"] = (val / 1000.0) * 60.0 if "ml" in unit else val

            m_f = re.search(r"(bioavailability|absolute bioavailability)[^0-9\n\r\:]*?([0-9]{1,3})\s*%?", raw, re.I)
            if m_f:
                val = float(m_f.group(2))
                out["bioavailability"] = val / 100.0 if val > 1 else val
    except Exception:
        pass

    return out

def fetch_drug_pharmacokinetics(drug_name: str) -> Dict[str, Any]:
    pk = {"half_life_hr": None, "clearance_L_per_hr": None, "Vd_L": None, "bioavailability": None, "sources": {}}

    try:
        dm = fetch_from_dailymed(drug_name)
        pk["sources"]["dailymed"] = dm.get("raw")
        for k in ("half_life_hr", "clearance_L_per_hr", "Vd_L", "bioavailability"):
            if pk[k] is None and dm.get(k) is not None:
                pk[k] = dm.get(k)
    except Exception:
        pass

    try:
        pc = fetch_from_pubchem(drug_name)
        pk["sources"]["pubchem"] = pc.get("raw")
        for k in ("half_life_hr", "clearance_L_per_hr", "Vd_L", "bioavailability"):
            if pk[k] is None and pc.get(k) is not None:
                pk[k] = pc.get(k)
    except Exception:
        pass

    try:
        if pk["half_life_hr"] is None and pk["Vd_L"] is not None and pk["clearance_L_per_hr"] is not None:
            pk["half_life_hr"] = 0.693 * (pk["Vd_L"] / pk["clearance_L_per_hr"])
    except Exception:
        pass

    return pk


# simulation core
def predict_concentration_timecourse(
    drug_params: Dict[str, Optional[float]],
    dosing_mg: float,
    dosing_interval_hr: float,
    num_doses: int,
    absorption_rate_hr: Optional[float] = None,
    body_weight_kg: Optional[float] = None,
    t_end_hr: Optional[float] = None,
    dt_hr: float = 0.1
) -> Tuple[List[float], List[float]]:
    half = drug_params.get("half_life_hr")
    CL = drug_params.get("clearance_L_per_hr")
    Vd = drug_params.get("Vd_L")
    F = drug_params.get("bioavailability")

    if F is None:
        F = 0.5 if absorption_rate_hr else 1.0

    if Vd is None and body_weight_kg:
        Vd = 0.6 * body_weight_kg

    if CL is None and half and Vd:
        CL = 0.693 * Vd / half

    if CL is None or Vd is None:
        raise ValueError("Insufficient PK parameters: need Vd_L and clearance_L_per_hr (or half_life and one of them)")

    kel = CL / Vd
    if half is None:
        half = 0.693 / kel

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
        for td in dose_times:
            if abs(t - td) < dt_hr / 2.0:
                if ka is not None:
                    A_gut_mg += dosing_mg
                else:
                    A_central_mg += dosing_mg * F

        if ka is not None:
            absorbed = ka * A_gut_mg * dt_hr
            if absorbed > A_gut_mg:
                absorbed = A_gut_mg
            A_gut_mg -= absorbed
            A_central_mg += absorbed * F

        elim = (CL / Vd) * A_central_mg * dt_hr
        if elim > A_central_mg:
            elim = A_central_mg
        A_central_mg -= elim

        C = (A_central_mg / Vd) if Vd > 0 else 0.0
        times.append(round(t, 6))
        conc.append(C)
        t += dt_hr

    return times, conc


def evaluate_therapeutic_window(times: List[float], conc: List[float], therapeutic_min_mg_per_L: float, therapeutic_max_mg_per_L: float) -> Dict[str, Any]:
    if len(times) != len(conc):
        raise ValueError("times and conc must be same length")

    total = 0.0
    below = within = above = 0.0
    for i in range(len(times) - 1):
        dt = times[i + 1] - times[i]
        total += dt
        c = conc[i]
        if c < therapeutic_min_mg_per_L:
            below += dt
        elif c > therapeutic_max_mg_per_L:
            above += dt
        else:
            within += dt

    pct_below = (below / total * 100.0) if total > 0 else 0.0
    pct_within = (within / total * 100.0) if total > 0 else 0.0
    pct_above = (above / total * 100.0) if total > 0 else 0.0

    alerts: List[str] = []
    if pct_above > 5.0:
        alerts.append("HIGH_RISK: concentration above therapeutic max for >5% of period")
    if pct_below > 20.0:
        alerts.append("LOW_RISK: concentration below therapeutic min for >20% of period")
    if pct_within < 50.0:
        alerts.append("SUBOPTIMAL: concentration within therapeutic window <50% of period")

    return {
        "pct_below": pct_below,
        "pct_within": pct_within,
        "pct_above": pct_above,
        "time_below_hr": below,
        "time_within_hr": within,
        "time_above_hr": above,
        "alerts": alerts,
    }


def build_drug_params_from_db(med: Medication, fallback_weight_kg: Optional[float] = None) -> Dict[str, Optional[float]]:
    half = _dec_to_float(med.half_life_hr)
    cl = _dec_to_float(med.clearance_l_hr)
    vd = _dec_to_float(med.volume_of_distribution_l)
    f = _dec_to_float(med.bioavailability_f)

    if vd is None and fallback_weight_kg:
        vd = 0.6 * fallback_weight_kg

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
    if all(v is not None for v in params.values()):
        return

    fetched = fetch_drug_pharmacokinetics(med.name)

    if med.half_life_hr is None and fetched.get("half_life_hr") is not None:
        med.half_life_hr = _float_to_dec(fetched["half_life_hr"])
    if med.clearance_l_hr is None and fetched.get("clearance_L_per_hr") is not None:
        med.clearance_l_hr = _float_to_dec(fetched["clearance_L_per_hr"])
    if med.volume_of_distribution_l is None and fetched.get("Vd_L") is not None:
        med.volume_of_distribution_l = _float_to_dec(fetched["Vd_L"])
    if med.bioavailability_f is None and fetched.get("bioavailability") is not None:
        med.bioavailability_f = _float_to_dec(fetched["bioavailability"])

    session.add(med)
    session.commit()

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

    weight_kg = _dec_to_float(pat.weight_kg) or (float(pat.weight) if pat.weight is not None else None)
    drug_params = build_drug_params_from_db(med, fallback_weight_kg=weight_kg)

    times, conc = predict_concentration_timecourse(
        drug_params=drug_params,
        dosing_mg=dose_mg,
        dosing_interval_hr=interval_hr,
        num_doses=num_doses,
        absorption_rate_hr=absorption_rate_hr,
        body_weight_kg=weight_kg,
        dt_hr=dt_hr,
    )

    tw_low = _dec_to_float(med.therapeutic_window_lower_mg_l) or 0.0
    tw_high = _dec_to_float(med.therapeutic_window_upper_mg_l) or 1e9
    eval_res = evaluate_therapeutic_window(times, conc, tw_low, tw_high)

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
            "times_hr": times[:2000],
            "conc_mg_per_L": conc[:2000],
            "therapeutic_eval": eval_res,
            "params_used": drug_params,
        },
    )

    session.add(sim)
    session.commit()
    session.refresh(sim)
    return sim
