"""Next-day maximum-temperature prediction using the exported Colab model."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from app.ml import feature_engineering as fe
from app.ml.model_loader import registry
from app.services import weather_service as ws


def build_live_features(city: str, basis: str = "today") -> dict:
    """Features for the cutoff day, computed with the training feature code."""
    raw, meta = ws.get_city_raw(city)
    daily = ws.daily_frame_from_hourly(raw)
    now = ws.local_now(raw)
    cutoff = now.normalize() if basis == "today" else now.normalize() - pd.Timedelta(days=1)
    c = fe.CITIES[city]
    x = fe.feature_row_for_date(daily, c["lat"], c["lon"], cutoff)

    hf = ws.hourly_frame(raw)
    on_day = hf[hf["time"].dt.normalize() == cutoff]
    forecast_hours = int((on_day["time"] > now).sum())
    return {"raw": raw, "meta": meta, "x": x, "cutoff": cutoff, "now": now,
            "forecast_hours_in_cutoff_day": forecast_hours}


def _ood_warnings(x: pd.DataFrame) -> list[str]:
    stats = registry.schema.get("feature_stats", {})
    out = []
    for f in fe.FEATURES:
        s = stats.get(f)
        if not s:
            continue
        v = float(x.iloc[0][f])
        span = max(s["max"] - s["min"], 1e-9)
        if v < s["min"] - 0.1 * span or v > s["max"] + 0.1 * span:
            out.append(f"{f}={v:.2f} is outside the range seen in training ({s['min']:.2f}..{s['max']:.2f})")
    return out



def _model_outputs(city: str, x: pd.DataFrame, target_date: pd.Timestamp) -> dict:
    """Run the trained model on one feature row (shared by live and manual modes)."""
    pred = float(np.asarray(registry.model.predict(x)).ravel()[0])
    if not np.isfinite(pred):
        raise ValueError("model returned a non-finite prediction")
    normal = registry.normal_for(city, target_date)
    category = fe.classify_heat(pred, normal["normal_tmax_c"], normal["p90_tmax_c"], normal["p95_tmax_c"])
    pi = registry.metrics.get("prediction_interval")
    interval = None
    if pi:
        interval = {
            "level": pi.get("level"),
            "lower_c": round(pred + pi["lower_offset"], 1),
            "upper_c": round(pred + pi["upper_offset"], 1),
            "calibrated_on": pi.get("calibrated_on"),
            "test_coverage": pi.get("test_coverage"),
            "method": pi.get("method"),
        }
    return {"pred": pred, "normal": normal, "category": category, "interval": interval}


def predict_city(city: str, basis: str = "today") -> dict:
    registry.require()
    ctx = build_live_features(city, basis)
    x: pd.DataFrame = ctx["x"]
    cutoff: pd.Timestamp = ctx["cutoff"]
    target_date = cutoff + pd.Timedelta(days=1)

    out = _model_outputs(city, x, target_date)
    pred, normal, category, interval = out["pred"], out["normal"], out["category"], out["interval"]

    raw = ctx["raw"]
    nwp = None
    d = raw.get("daily", {})
    tstr = target_date.strftime("%Y-%m-%d")
    if tstr in d.get("time", []):
        nwp = d["temperature_2m_max"][d["time"].index(tstr)]

    warnings = list(registry.warnings) + _ood_warnings(x)
    if ctx["forecast_hours_in_cutoff_day"] > 0:
        warnings.append(
            f"The cutoff day is still in progress: {ctx['forecast_hours_in_cutoff_day']} of its 24 hourly "
            "values come from the weather-model forecast rather than from past hours.")

    return {
        "city": city,
        "model": {
            "name": registry.model_name,
            "selected_by": "lowest validation MAE",
            "trained_on": registry.metadata.get("dataset", {}).get("period"),
        },
        "prediction": {
            "target": "next-day maximum 2 m air temperature",
            "predicted_tmax_c": round(pred, 1),
            "prediction_date": tstr,
            "cutoff_date": cutoff.strftime("%Y-%m-%d"),
            "basis": basis,
            "interval": interval,
        },
        "climatology": {
            "baseline_period": "1991-2020",
            "product": registry.metadata.get("climate_normals", {}).get("product"),
            "window_days": registry.metadata.get("climate_normals", {}).get("window_days"),
            "seasonal_normal_c": round(normal["normal_tmax_c"], 1),
            "p90_c": round(normal["p90_tmax_c"], 1),
            "p95_c": round(normal["p95_tmax_c"], 1),
            "anomaly_c": category["anomaly_c"],
        },
        "heat_risk": {k: category[k] for k in ("level", "label", "color", "rule", "disclaimer")},
        "reference_nwp_forecast_tmax_c": nwp,
        "reference_note": "Open-Meteo's own weather-model forecast for the same day, shown only for comparison. "
                          "It is NOT an input to the machine-learning model.",
        "features_used": {f: round(float(x.iloc[0][f]), 3) for f in fe.FEATURES},
        "timestamps": {
            "fetched_at_utc": raw.get("_fetched_at_utc"),
            "local_now": ctx["now"].strftime("%Y-%m-%dT%H:%M"),
        },
        "cache": ctx["meta"],
        "warnings": warnings,
        "disclaimer": "This is a short-range statistical weather forecast. It does not attribute "
                      "temperature changes to greenhouse gases.",
    }


def predict_all(basis: str = "today") -> dict:
    registry.require()
    results, errors = [], {}

    def one(c):
        try:
            return c, predict_city(c, basis), None
        except Exception as exc:  # per-city failure must not hide other cities
            return c, None, str(exc)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for c, res, err in ex.map(one, list(fe.CITIES)):
            if res:
                results.append(res)
            else:
                errors[c] = err
    return {"cities": results, "errors": errors}


MANUAL_FIELDS = ["tmax_d0", "tmin_d0", "tmax_d1", "tmax_d2", "tmin_d1", "rh_mean_d0", "precip_d0",
                 "precip_sum3", "wind_mean_d0", "solar_mj_d0", "pressure_mean_d0", "cloud_mean_d0", "tmax_roll7"]


def build_manual_features(city: str, cutoff_date: str, values: dict) -> pd.DataFrame:
    """One feature row from typed values. Derived columns use the SAME formulas as training."""
    c = fe.CITIES[city]
    cutoff = pd.Timestamp(cutoff_date).normalize()
    doy = fe.day_of_year_365([cutoff + pd.Timedelta(days=1)])[0]
    row = {k: float(values[k]) for k in MANUAL_FIELDS}
    row["tmax_roll3"] = (row["tmax_d0"] + row["tmax_d1"] + row["tmax_d2"]) / 3.0
    row["doy_sin"] = float(np.sin(2 * np.pi * doy / 365.0))
    row["doy_cos"] = float(np.cos(2 * np.pi * doy / 365.0))
    row["latitude"], row["longitude"] = float(c["lat"]), float(c["lon"])
    return pd.DataFrame([row])[fe.FEATURES].astype(float)


def predict_manual(city: str, cutoff_date: str, values: dict, with_explanation: bool = True) -> dict:
    """What-if prediction from user-typed inputs, using the same trained model and code path."""
    registry.require()
    cutoff = pd.Timestamp(cutoff_date).normalize()
    target_date = cutoff + pd.Timedelta(days=1)
    x = build_manual_features(city, cutoff_date, values)
    out = _model_outputs(city, x, target_date)
    pred, normal, category, interval = out["pred"], out["normal"], out["category"], out["interval"]

    warnings = list(registry.warnings) + _ood_warnings(x)
    if abs(values["tmax_roll7"] - float(x.iloc[0]["tmax_roll3"])) > 8:
        warnings.append("tmax_roll7 differs a lot from the 3-day mean - please double-check the 7-day mean.")
    warnings.append("Manual what-if run: the numbers were typed in by the user, not fetched from a weather source.")

    explanation = None
    if with_explanation:
        from app.services.explanation_service import explain_row
        explanation = explain_row(x, city, target_date)

    return {
        "mode": "manual",
        "city": city,
        "model": {"name": registry.model_name, "selected_by": "lowest validation MAE",
                  "trained_on": registry.metadata.get("dataset", {}).get("period")},
        "prediction": {
            "target": "next-day maximum 2 m air temperature",
            "predicted_tmax_c": round(pred, 1),
            "prediction_date": target_date.strftime("%Y-%m-%d"),
            "cutoff_date": cutoff.strftime("%Y-%m-%d"),
            "basis": "manual",
            "interval": interval,
        },
        "climatology": {
            "baseline_period": "1991-2020",
            "product": registry.metadata.get("climate_normals", {}).get("product"),
            "window_days": registry.metadata.get("climate_normals", {}).get("window_days"),
            "seasonal_normal_c": round(normal["normal_tmax_c"], 1),
            "p90_c": round(normal["p90_tmax_c"], 1),
            "p95_c": round(normal["p95_tmax_c"], 1),
            "anomaly_c": category["anomaly_c"],
        },
        "heat_risk": {k: category[k] for k in ("level", "label", "color", "rule", "disclaimer")},
        "reference_nwp_forecast_tmax_c": None,
        "features_used": {f: round(float(x.iloc[0][f]), 3) for f in fe.FEATURES},
        "derived_features": {
            "tmax_roll3": "mean of tmax_d0, tmax_d1, tmax_d2",
            "doy_sin / doy_cos": "from the target day's day-of-year",
            "latitude / longitude": f"fixed city coordinates for {city}",
        },
        "explanation": explanation,
        "warnings": warnings,
        "disclaimer": "What-if result of the trained model for the values you typed. It is a statistical "
                      "weather estimate, not an official forecast, and says nothing about greenhouse-gas causation.",
    }
