from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TherapeuticTargets:
    max_pct_below: float = 20.0
    max_pct_above: float = 5.0
    min_pct_within: float = 50.0


DEFAULT_TARGETS = TherapeuticTargets()


def evaluate_therapeutic_window(
    times_hr: List[float],
    conc_mg_per_L: List[float],
    lower_mg_per_L: float,
    upper_mg_per_L: float,
    t_start_hr: Optional[float] = None,
    t_end_hr: Optional[float] = None,
    targets: TherapeuticTargets = DEFAULT_TARGETS,
) -> Dict[str, Any]:
    if (
        not times_hr
        or not conc_mg_per_L
        or len(times_hr) != len(conc_mg_per_L)
        or len(times_hr) < 2
    ):
        return _empty_eval("Insufficient data to evaluate therapeutic window.", targets)

    if lower_mg_per_L < 0 or upper_mg_per_L <= lower_mg_per_L:
        return _empty_eval("Invalid therapeutic window bounds.", targets)

    total = 0.0
    below = 0.0
    within = 0.0
    above = 0.0

    for i in range(len(times_hr) - 1):
        seg_start = times_hr[i]
        seg_end = times_hr[i + 1]
        dt = seg_end - seg_start
        if dt <= 0:
            continue

        mid_t = 0.5 * (seg_start + seg_end)
        if t_start_hr is not None and mid_t < t_start_hr:
            continue
        if t_end_hr is not None and mid_t > t_end_hr:
            continue

        total += dt
        c_mid = 0.5 * (conc_mg_per_L[i] + conc_mg_per_L[i + 1])
        if c_mid < lower_mg_per_L:
            below += dt
        elif c_mid > upper_mg_per_L:
            above += dt
        else:
            within += dt

    if total <= 0:
        return _empty_eval("Evaluation window contains no usable samples.", targets)

    pct_below = 100.0 * below / total
    pct_within = 100.0 * within / total
    pct_above = 100.0 * above / total

    below_gap_pct = max(0.0, pct_below - targets.max_pct_below)
    above_gap_pct = max(0.0, pct_above - targets.max_pct_above)
    within_gap_pct = max(0.0, targets.min_pct_within - pct_within)

    below_score = below_gap_pct / targets.max_pct_below if targets.max_pct_below > 0 else 0.0
    above_score = above_gap_pct / targets.max_pct_above if targets.max_pct_above > 0 else 0.0
    within_score = within_gap_pct / targets.min_pct_within if targets.min_pct_within > 0 else 0.0
    off_score = max(below_score, above_score, within_score)

    if off_score == 0.0:
        risk = "NONE"
    elif off_score <= 0.5:
        risk = "LOW"
    elif off_score <= 1.5:
        risk = "MODERATE"
    else:
        risk = "HIGH"

    alerts: List[str] = []
    if pct_above > targets.max_pct_above:
        alerts.append(
            f"HIGH_RISK: above therapeutic max for {pct_above:.1f}% "
            f"(target <= {targets.max_pct_above:.1f}%)."
        )
    if pct_below > targets.max_pct_below:
        alerts.append(
            f"LOW_RISK: below therapeutic min for {pct_below:.1f}% "
            f"(target <= {targets.max_pct_below:.1f}%)."
        )
    if pct_within < targets.min_pct_within:
        alerts.append(
            f"SUBOPTIMAL: within therapeutic window for {pct_within:.1f}% "
            f"(target >= {targets.min_pct_within:.1f}%)."
        )

    return {
        "pct_below": pct_below,
        "pct_within": pct_within,
        "pct_above": pct_above,
        "time_below_hr": below,
        "time_within_hr": within,
        "time_above_hr": above,
        "alerts": alerts,
        "target_below_pct": targets.max_pct_below,
        "target_above_pct": targets.max_pct_above,
        "target_within_pct": targets.min_pct_within,
        "below_gap_pct": below_gap_pct,
        "above_gap_pct": above_gap_pct,
        "within_gap_pct": within_gap_pct,
        "off_score": off_score,
        "ade_risk_level": risk,
    }


def _empty_eval(message: str, targets: TherapeuticTargets) -> Dict[str, Any]:
    return {
        "pct_below": 0.0,
        "pct_within": 0.0,
        "pct_above": 0.0,
        "time_below_hr": 0.0,
        "time_within_hr": 0.0,
        "time_above_hr": 0.0,
        "alerts": [message],
        "target_below_pct": targets.max_pct_below,
        "target_above_pct": targets.max_pct_above,
        "target_within_pct": targets.min_pct_within,
        "below_gap_pct": 0.0,
        "above_gap_pct": 0.0,
        "within_gap_pct": 0.0,
        "off_score": 0.0,
        "ade_risk_level": "UNKNOWN",
    }
