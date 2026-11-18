"""Global (from notebook) and local (computed live) explanations."""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.ml import feature_engineering as fe
from app.ml.explain_core import permutation_shapley
from app.ml.model_loader import registry
from app.services.prediction_service import build_live_features


def global_explanations() -> dict:
    registry.require()
    return registry.importance


def explain_row(x: pd.DataFrame, city: str, target_date) -> dict:
    """Local explanation for ONE feature row (live or manual)."""
    registry.require()
    baseline_vals = registry.schema.get("baseline")
    if not baseline_vals:
        raise RuntimeError("feature_schema.json has no training baseline")
    baseline = pd.Series(baseline_vals)
    res = permutation_shapley(registry.model, x.iloc[0], baseline, fe.FEATURES,
                              n_permutations=settings.shap_permutations, seed=42)
    items = []
    for f in fe.FEATURES:
        items.append({
            "feature": f,
            "label": fe.FEATURE_INFO[f][0],
            "unit": fe.FEATURE_INFO[f][1],
            "value": round(float(x.iloc[0][f]), 3),
            "baseline_value": round(float(baseline[f]), 3),
            "contribution_c": round(res["contributions"][f], 3),
        })
    items.sort(key=lambda r: abs(r["contribution_c"]), reverse=True)
    return {
        "city": city,
        "prediction_date": pd.Timestamp(target_date).strftime("%Y-%m-%d"),
        "model": registry.model_name,
        "base_value_c": round(res["base_value"], 2),
        "predicted_tmax_c": round(res["prediction"], 2),
        "method": res["method"],
        "reading_guide": "Contributions are in °C relative to the average training-set input. "
                         "Positive = pushes the predicted maximum up; negative = pushes it down. "
                         "They add up to (prediction - base value).",
        "increasing": [i for i in items if i["contribution_c"] > 0],
        "decreasing": [i for i in items if i["contribution_c"] < 0],
        "all": items,
    }


def local_explanation(city: str, basis: str = "today") -> dict:
    registry.require()
    ctx = build_live_features(city, basis)
    out = explain_row(ctx["x"], city, ctx["cutoff"] + pd.Timedelta(days=1))
    out["timestamps"] = {"fetched_at_utc": ctx["raw"].get("_fetched_at_utc")}
    return out
