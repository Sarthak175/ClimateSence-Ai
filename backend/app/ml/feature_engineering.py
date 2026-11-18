"""ClimateSense AI - shared feature engineering (SINGLE SOURCE OF TRUTH).

This exact file is used in two places:
  1. the Google Colab training notebook (it is written to disk by the notebook), and
  2. the FastAPI backend (live inference).

Keeping one file guarantees that training features and live-inference features are
computed by identical code (no train/serve skew).

Prediction task
---------------
Cutoff day D  ->  predict the MAXIMUM 2 m air temperature of day D+1.
Only information from days <= D is used. The only forward-looking column is
`target_tmax`, which is NEVER part of FEATURES.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_MODULE_VERSION = "1.0.0"
TIMEZONE = "Asia/Kolkata"

# City name -> coordinates (decimal degrees). Used for training AND serving.
CITIES = {
    "Chennai": {"lat": 13.0827, "lon": 80.2707},
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639},
}

# Hourly variables that the model needs (names follow the Open-Meteo API).
MODEL_HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "wind_speed_10m",
    "surface_pressure",
    "cloud_cover",
    "shortwave_radiation",
]

# Expected units from the Open-Meteo API (validated in training and live).
EXPECTED_UNITS = {
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
    "wind_speed_10m": "km/h",
    "surface_pressure": "hPa",
    "cloud_cover": "%",
    "shortwave_radiation": "W/m²",
}

# Model input columns, in this exact order.
FEATURES = [
    "tmax_d0",
    "tmin_d0",
    "tmax_d1",
    "tmax_d2",
    "tmin_d1",
    "rh_mean_d0",
    "precip_d0",
    "precip_sum3",
    "wind_mean_d0",
    "solar_mj_d0",
    "pressure_mean_d0",
    "cloud_mean_d0",
    "tmax_roll3",
    "tmax_roll7",
    "doy_sin",
    "doy_cos",
    "latitude",
    "longitude",
]
TARGET = "target_tmax"

FEATURE_INFO = {
    "tmax_d0": ("Max temperature, cutoff day", "°C"),
    "tmin_d0": ("Min temperature, cutoff day", "°C"),
    "tmax_d1": ("Max temperature, 1 day before cutoff", "°C"),
    "tmax_d2": ("Max temperature, 2 days before cutoff", "°C"),
    "tmin_d1": ("Min temperature, 1 day before cutoff", "°C"),
    "rh_mean_d0": ("Mean relative humidity, cutoff day", "%"),
    "precip_d0": ("Precipitation total, cutoff day", "mm"),
    "precip_sum3": ("Precipitation total, last 3 days", "mm"),
    "wind_mean_d0": ("Mean wind speed (10 m), cutoff day", "km/h"),
    "solar_mj_d0": ("Shortwave solar radiation total, cutoff day", "MJ/m²"),
    "pressure_mean_d0": ("Mean surface pressure, cutoff day", "hPa"),
    "cloud_mean_d0": ("Mean cloud cover, cutoff day", "%"),
    "tmax_roll3": ("3-day rolling mean of max temperature", "°C"),
    "tmax_roll7": ("7-day rolling mean of max temperature", "°C"),
    "doy_sin": ("Seasonality: sin(2π·day-of-year/365) of target day", "-"),
    "doy_cos": ("Seasonality: cos(2π·day-of-year/365) of target day", "-"),
    "latitude": ("Latitude of the city", "°"),
    "longitude": ("Longitude of the city", "°"),
}

# Project-defined heat categories (NOT official IMD warnings).
ANOMALY_ELEVATED_C = 1.5
HEAT_LEVELS = [
    {"level": 0, "label": "Normal", "color": "#2dd4bf",
     "rule": "Predicted max < normal + 1.5 °C and below the 90th percentile"},
    {"level": 1, "label": "Elevated", "color": "#facc15",
     "rule": "Anomaly >= +1.5 °C but below the 90th percentile of the city's seasonal window"},
    {"level": 2, "label": "High", "color": "#fb923c",
     "rule": "Predicted max >= 90th percentile of the city's seasonal window"},
    {"level": 3, "label": "Severe", "color": "#ef4444",
     "rule": "Predicted max >= 95th percentile of the city's seasonal window"},
]
HEAT_DISCLAIMER = (
    "Project-defined heat categories derived from a 1991-2020 ERA5-Land climatology. "
    "They are NOT official India Meteorological Department (IMD) warnings."
)


class FeatureError(ValueError):
    """Raised when features cannot be built honestly (missing / incomplete data)."""


def day_of_year_365(dates) -> np.ndarray:
    """Day of year on a fixed 365-day calendar (29 Feb is mapped onto 28 Feb)."""
    idx = pd.DatetimeIndex(dates)
    doy = np.asarray(idx.dayofyear, dtype=int).copy()
    leap_after_feb = np.asarray(idx.is_leap_year) & (doy >= 60)
    return np.where(leap_after_feb, doy - 1, doy)


def validate_units(units: dict | None) -> list[str]:
    """Return a list of unit problems (empty list = all units as expected)."""
    problems = []
    if not units:
        return ["no units returned by API"]
    for var, expected in EXPECTED_UNITS.items():
        got = units.get(var)
        if got is None:
            problems.append(f"{var}: unit missing")
        elif got.replace(" ", "") != expected.replace(" ", ""):
            problems.append(f"{var}: expected {expected}, got {got}")
    return problems


def hourly_to_daily(hourly: pd.DataFrame, min_hours: int = 22) -> pd.DataFrame:
    """Aggregate hourly API data into local-calendar-day records.

    `hourly` needs a `time` column (local time, as returned with timezone=Asia/Kolkata)
    plus the MODEL_HOURLY_VARIABLES. Days with fewer than `min_hours` valid temperature
    values are dropped (never filled / invented).
    """
    missing = [c for c in ["time", *MODEL_HOURLY_VARIABLES] if c not in hourly.columns]
    if missing:
        raise FeatureError(f"hourly data lacks columns: {missing}")
    df = hourly[["time", *MODEL_HOURLY_VARIABLES]].copy()
    df["time"] = pd.to_datetime(df["time"])
    df["date"] = df["time"].dt.normalize()
    g = df.groupby("date")
    daily = pd.DataFrame(
        {
            "tmax": g["temperature_2m"].max(),
            "tmin": g["temperature_2m"].min(),
            "rh_mean": g["relative_humidity_2m"].mean(),
            "precip_sum": g["precipitation"].sum(min_count=1),
            "wind_mean": g["wind_speed_10m"].mean(),
            "pressure_mean": g["surface_pressure"].mean(),
            "cloud_mean": g["cloud_cover"].mean(),
            # hourly mean W/m2 x 3600 s = J/m2 per hour; sum -> MJ/m2
            "solar_mj": g["shortwave_radiation"].sum(min_count=1) * 3600.0 / 1e6,
            "n_hours": g["temperature_2m"].count(),
        }
    )
    daily = daily[daily["n_hours"] >= min_hours]
    return daily.reset_index()


def make_feature_frame(daily: pd.DataFrame, latitude: float, longitude: float) -> pd.DataFrame:
    """Build model features (and the training target) from one city's daily table.

    Row for date D contains ONLY information from days <= D. `target_tmax` is the
    max temperature of D+1 (NaN for the most recent day) and is never a feature.
    """
    d = daily.sort_values("date").drop_duplicates("date").set_index("date")
    if d.empty:
        raise FeatureError("daily table is empty")
    # calendar-continuous index so lags/rolling windows are true calendar days
    d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"))

    f = pd.DataFrame(index=d.index)
    f["tmax_d0"] = d["tmax"]
    f["tmin_d0"] = d["tmin"]
    f["tmax_d1"] = d["tmax"].shift(1)
    f["tmax_d2"] = d["tmax"].shift(2)
    f["tmin_d1"] = d["tmin"].shift(1)
    f["rh_mean_d0"] = d["rh_mean"]
    f["precip_d0"] = d["precip_sum"]
    f["precip_sum3"] = d["precip_sum"].rolling(3, min_periods=3).sum()
    f["wind_mean_d0"] = d["wind_mean"]
    f["solar_mj_d0"] = d["solar_mj"]
    f["pressure_mean_d0"] = d["pressure_mean"]
    f["cloud_mean_d0"] = d["cloud_mean"]
    f["tmax_roll3"] = d["tmax"].rolling(3, min_periods=3).mean()
    f["tmax_roll7"] = d["tmax"].rolling(7, min_periods=7).mean()

    target_dates = f.index + pd.Timedelta(days=1)
    doy = day_of_year_365(target_dates)
    f["doy_sin"] = np.sin(2 * np.pi * doy / 365.0)
    f["doy_cos"] = np.cos(2 * np.pi * doy / 365.0)
    f["latitude"] = float(latitude)
    f["longitude"] = float(longitude)

    f[TARGET] = d["tmax"].shift(-1)  # <- the only forward-looking column
    f.index.name = "date"
    f = f.reset_index()
    f["target_date"] = f["date"] + pd.Timedelta(days=1)
    return f[["date", "target_date", *FEATURES, TARGET]]


def feature_row_for_date(daily: pd.DataFrame, latitude: float, longitude: float, cutoff_date) -> pd.DataFrame:
    """One-row DataFrame (columns == FEATURES) for live inference at `cutoff_date`."""
    frame = make_feature_frame(daily, latitude, longitude)
    cutoff = pd.Timestamp(cutoff_date).normalize()
    row = frame[frame["date"] == cutoff]
    if row.empty:
        raise FeatureError(f"no daily record available for cutoff date {cutoff.date()}")
    x = row[FEATURES].astype(float)
    bad = [c for c in FEATURES if not np.isfinite(x.iloc[0][c])]
    if bad:
        raise FeatureError(f"missing / non-finite features for {cutoff.date()}: {bad}")
    return x.reset_index(drop=True)


def classify_heat(predicted: float, normal: float, p90: float, p95: float) -> dict:
    """Project-defined heat category (see HEAT_LEVELS)."""
    anomaly = float(predicted) - float(normal)
    if predicted >= p95:
        level = 3
    elif predicted >= p90:
        level = 2
    elif anomaly >= ANOMALY_ELEVATED_C:
        level = 1
    else:
        level = 0
    info = dict(HEAT_LEVELS[level])
    info["anomaly_c"] = round(anomaly, 2)
    info["disclaimer"] = HEAT_DISCLAIMER
    return info


def feature_schema_entries() -> list[dict]:
    return [
        {"name": n, "label": FEATURE_INFO[n][0], "unit": FEATURE_INFO[n][1]} for n in FEATURES
    ]
