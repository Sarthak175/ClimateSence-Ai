"""Automatic 'is this model good enough?' gate, computed from the REAL metrics written by the notebook.

The thresholds below are project policy (documented in the UI); the numbers they are compared with
come only from model_metrics.json. Nothing here invents a metric.
"""
from __future__ import annotations

POLICY = {
    "min_train_rows": 3000,
    "min_test_rows": 500,
    "min_improvement_over_persistence_pct": 5.0,
    "min_test_r2": 0.80,
    "max_test_mae_c": 1.5,
    "interval_coverage_range": (0.80, 0.97),
    "max_test_to_validation_mae_ratio": 2.0,
    "max_city_mae_ratio": 1.6,
    "min_heat_event_recall": 0.5,
}


def _g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def _check(name, ok, value, rule, hard):
    return {"name": name, "passed": bool(ok) if ok is not None else None, "value": value, "rule": rule,
            "severity": "required" if hard else "advisory"}


def assess(m: dict) -> dict:
    test = _g(m, "best_model", "test", default={}) or {}
    val = _g(m, "best_model", "validation", default={}) or {}
    n_tr, n_te = _g(m, "split", "train", "n_rows"), _g(m, "split", "test", "n_rows")
    imp = _g(m, "improvement_over_persistence_pct", "test_mae")
    cov = _g(m, "prediction_interval", "test_coverage")
    rec = _g(m, "heat_event_detection", "recall")
    city = _g(m, "per_city_test_mae", default={}) or {}
    lo, hi = POLICY["interval_coverage_range"]
    r = lambda x, n=3: None if x is None else round(float(x), n)  # noqa: E731

    checks = [
        _check("Enough training data", n_tr is not None and n_tr >= POLICY["min_train_rows"], n_tr,
               f"≥ {POLICY['min_train_rows']} training rows", True),
        _check("Enough unseen test data", n_te is not None and n_te >= POLICY["min_test_rows"], n_te,
               f"≥ {POLICY['min_test_rows']} test rows", True),
        _check("Beats the persistence baseline", imp is not None and imp >= POLICY["min_improvement_over_persistence_pct"],
               r(imp, 1), f"test MAE at least {POLICY['min_improvement_over_persistence_pct']} % better than 'tomorrow = today'", True),
        _check("Explains the variance (R²)", test.get("r2") is not None and test["r2"] >= POLICY["min_test_r2"],
               r(test.get("r2")), f"test R² ≥ {POLICY['min_test_r2']}", True),
        _check("Typical error is small", test.get("mae") is not None and test["mae"] <= POLICY["max_test_mae_c"],
               r(test.get("mae")), f"test MAE ≤ {POLICY['max_test_mae_c']} °C", True),
        _check("Prediction interval is honest", cov is not None and lo <= cov <= hi, r(cov),
               f"observed test coverage of the 90 % interval between {lo:.0%} and {hi:.0%}", True),
    ]
    ratio = (test["mae"] / val["mae"]) if test.get("mae") and val.get("mae") else None
    checks.append(_check("Generalises beyond validation", ratio is not None and ratio <= POLICY["max_test_to_validation_mae_ratio"],
                         r(ratio, 2), f"test MAE ≤ {POLICY['max_test_to_validation_mae_ratio']}× validation MAE", False))
    cmax = (max(city.values()) / (sum(city.values()) / len(city))) if city else None
    checks.append(_check("Works across all cities", cmax is not None and cmax <= POLICY["max_city_mae_ratio"],
                         r(cmax, 2), f"worst city MAE ≤ {POLICY['max_city_mae_ratio']}× the average city MAE", False))
    checks.append(_check("Detects heat events", rec is not None and rec >= POLICY["min_heat_event_recall"], r(rec),
                         f"recall of ≥P90 days ≥ {POLICY['min_heat_event_recall']}", False))

    req_fail = [c for c in checks if c["severity"] == "required" and not c["passed"]]
    adv_fail = [c for c in checks if c["severity"] == "advisory" and not c["passed"]]
    if req_fail:
        verdict, text = "not_ready", "Not good enough yet: treat predictions as experimental and retrain / improve the model."
    elif adv_fail:
        verdict, text = "limited", "Meets all required checks, with advisory weaknesses - use predictions with the listed caveats."
    else:
        verdict, text = "ready", "Meets all required and advisory checks on unseen test data."
    return {"verdict": verdict, "summary": text, "checks": checks, "policy_note":
            "Thresholds are project policy; every value shown is read from the notebook's model_metrics.json."}
