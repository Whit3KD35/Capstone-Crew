from app.pharmacokinetics import compute_prediction_accuracy_metrics, evaluate_therapeutic_window
from app.pk_scoring import TherapeuticTargets


def test_therapeutic_window_returns_expected_keys():
    times = [0.0, 1.0, 2.0, 3.0]
    conc = [0.5, 1.5, 2.5, 0.9]
    res = evaluate_therapeutic_window(
        times=times,
        conc=conc,
        therapeutic_min_mg_per_L=1.0,
        therapeutic_max_mg_per_L=2.0,
        targets=TherapeuticTargets(max_pct_below=20.0, max_pct_above=10.0, min_pct_within=50.0),
    )
    assert "pct_below" in res
    assert "pct_within" in res
    assert "pct_above" in res
    assert "ade_risk_level" in res
    assert "off_score" in res


def test_prediction_accuracy_metrics_basic():
    observed = [10.0, 20.0, 30.0]
    predicted = [11.0, 18.0, 33.0]
    res = compute_prediction_accuracy_metrics(observed, predicted)
    assert res["n_total"] == 3.0
    assert res["n_nonzero_observed"] == 3.0
    assert res["p20_pct"] > 0
    assert res["p30_pct"] > 0
