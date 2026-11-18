"""TEST-ONLY synthetic data generators.

!!! These generate artificial weather purely to exercise the code paths in automated
tests. Nothing here is ever shipped as data, model, or metric of the project. !!!
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml import feature_engineering as fe

UNITS = {"time": "iso8601", "temperature_2m": "°C", "relative_humidity_2m": "%", "precipitation": "mm",
         "wind_speed_10m": "km/h", "surface_pressure": "hPa", "cloud_cover": "%",
         "shortwave_radiation": "W/m²", "apparent_temperature": "°C"}


def synthetic_hourly(lat: float, start: str, end: str, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed + int(lat * 100))
    t = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    doy = t.dayofyear.values
    hour = t.hour.values
    seasonal = 29 + 6 * np.sin(2 * np.pi * (doy - 80) / 365) - 0.15 * (lat - 15)
    # slowly varying weather regime (autocorrelated)
    days = pd.date_range(t.min().normalize(), t.max().normalize(), freq="D")
    regime = np.cumsum(rng.normal(0, 0.8, len(days)))
    regime = regime - pd.Series(regime).rolling(15, min_periods=1, center=True).mean().values
    reg = pd.Series(regime, index=days).reindex(t.normalize()).values
    diurnal = -5 * np.cos(2 * np.pi * (hour - 3) / 24)
    temp = seasonal + reg + diurnal + rng.normal(0, 0.3, len(t))
    df = pd.DataFrame({
        "time": t,
        "temperature_2m": temp,
        "relative_humidity_2m": np.clip(70 - 1.5 * (temp - 28) + rng.normal(0, 4, len(t)), 5, 100),
        "precipitation": np.clip(rng.gamma(0.2, 1.0, len(t)) - 0.15, 0, None),
        "wind_speed_10m": np.clip(10 + rng.normal(0, 3, len(t)), 0, None),
        "surface_pressure": 1005 + rng.normal(0, 2, len(t)),
        "cloud_cover": np.clip(50 + rng.normal(0, 25, len(t)), 0, 100),
        "shortwave_radiation": np.clip(900 * np.sin(np.pi * (hour - 6) / 12), 0, None),
    })
    df["apparent_temperature"] = df["temperature_2m"] + 0.05 * df["relative_humidity_2m"] - 2
    return df


def hourly_json(df: pd.DataFrame) -> dict:
    d = {"time": df["time"].dt.strftime("%Y-%m-%dT%H:%M").tolist()}
    for c in df.columns:
        if c != "time":
            d[c] = [round(float(v), 2) for v in df[c]]
    return d


def forecast_response(lat: float, lon: float, today: pd.Timestamp, past=10, future=7) -> dict:
    start = (today - pd.Timedelta(days=past)).strftime("%Y-%m-%d")
    end = (today + pd.Timedelta(days=future - 1)).strftime("%Y-%m-%d")
    h = synthetic_hourly(lat, start, end, seed=1)
    daily = h.assign(date=h.time.dt.strftime("%Y-%m-%d")).groupby("date").agg(
        tmax=("temperature_2m", "max"), tmin=("temperature_2m", "min"),
        pr=("precipitation", "sum"), wi=("wind_speed_10m", "max"))
    now_row = h[h.time <= pd.Timestamp.utcnow().tz_convert(None) + pd.Timedelta(hours=5.5)].iloc[-1]
    return {
        "latitude": lat, "longitude": lon, "generationtime_ms": 0.4, "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "current_units": {"temperature_2m": "°C"},
        "current": {"time": now_row["time"].strftime("%Y-%m-%dT%H:%M"), "interval": 900,
                    "temperature_2m": float(now_row.temperature_2m),
                    "relative_humidity_2m": float(now_row.relative_humidity_2m),
                    "apparent_temperature": float(now_row.apparent_temperature),
                    "precipitation": 0.0, "wind_speed_10m": float(now_row.wind_speed_10m),
                    "surface_pressure": float(now_row.surface_pressure),
                    "cloud_cover": float(now_row.cloud_cover),
                    "shortwave_radiation": float(now_row.shortwave_radiation)},
        "hourly_units": UNITS, "hourly": hourly_json(h),
        "daily_units": {}, "daily": {
            "time": daily.index.tolist(), "temperature_2m_max": daily.tmax.round(1).tolist(),
            "temperature_2m_min": daily.tmin.round(1).tolist(), "precipitation_sum": daily.pr.round(1).tolist(),
            "wind_speed_10m_max": daily.wi.round(1).tolist()},
    }


def make_test_artifacts(out_dir: Path) -> None:
    """Train a tiny model on SYNTHETIC data purely so API tests can run offline."""
    import joblib
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, c in fe.CITIES.items():
        h = synthetic_hourly(c["lat"], "2023-01-01", "2024-12-31", seed=3)
        frames.append(fe.make_feature_frame(fe.hourly_to_daily(h), c["lat"], c["lon"]))
    df = pd.concat(frames).dropna()
    X, y = df[fe.FEATURES], df[fe.TARGET]
    model = Pipeline([("scaler", StandardScaler()), ("lr", LinearRegression())]).fit(X, y)
    joblib.dump(model, out_dir / "best_model.joblib")

    stats = {f: {"min": float(X[f].min()), "max": float(X[f].max()), "mean": float(X[f].mean()),
                 "median": float(X[f].median()), "std": float(X[f].std())} for f in fe.FEATURES}
    schema = {"features": fe.FEATURES, "feature_module_version": fe.FEATURE_MODULE_VERSION,
              "feature_module_sha256": None, "feature_stats": stats,
              "baseline": {f: stats[f]["mean"] for f in fe.FEATURES}, "details": fe.feature_schema_entries()}
    (out_dir / "feature_schema.json").write_text(json.dumps(schema))
    (out_dir / "model_metrics.json").write_text(json.dumps({
        "best_model": {"name": "Linear Regression (TEST FIXTURE)"}, "models": {}, "split": {},
        "prediction_interval": {"level": 0.9, "lower_offset": -2.0, "upper_offset": 2.0,
                                "calibrated_on": "validation", "test_coverage": 0.9, "method": "test"}}))
    (out_dir / "feature_importance.json").write_text(json.dumps({"best_model": "x", "permutation": {}}))
    (out_dir / "training_metadata.json").write_text(json.dumps({
        "dataset": {"period": "test"}, "climate_normals": {"product": "test", "window_days": 15},
        "environment": {}}))
    rows = []
    for city in fe.CITIES:
        for doy in range(1, 366):
            n = 29 + 6 * np.sin(2 * np.pi * (doy - 80) / 365)
            rows.append({"city": city, "doy": doy, "normal_tmax": n, "p90_tmax": n + 2.5,
                         "p95_tmax": n + 3.5, "std_tmax": 1.5, "n_samples": 450})
    pd.DataFrame(rows).to_csv(out_dir / "city_climate_normals.csv", index=False)
