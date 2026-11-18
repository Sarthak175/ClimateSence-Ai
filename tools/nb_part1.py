"""Notebook cells, sections 1-3."""
CELLS = []
def md(t): CELLS.append(("md", t.strip("\n")))
def code(t): CELLS.append(("code", t.strip("\n")))

md(r'''
# 🌍 ClimateSense AI — ML Training Notebook
**Live Urban Heat Island Monitoring, Climate Intelligence and ML-Based Temperature Prediction**
Third-year ML project · *Global Warming and Climate Change* · topic: **Urban Heat-Island Reduction**

### What this notebook does (and does not do)
| ✅ It does | ❌ It does not |
|---|---|
| Downloads **real** archived weather-model data (Open-Meteo Historical Forecast API) for 6 Indian cities | invent, simulate or randomly generate any weather value |
| Trains **Linear Regression, SVR (RBF), Random Forest** to predict *tomorrow's maximum temperature* | claim that this daily model *proves* greenhouse-gas causation |
| Evaluates with **MAE, MSE, R²** on a chronological validation and an untouched test set | hard-code any score — every number below is computed when you run the cells |
| Builds 1991–2020 **ERA5-Land climate normals** to compute temperature anomalies | |
| Explains the model (feature importance, permutation importance, SHAP) | |
| Exports everything the FastAPI backend needs | |

> **Weather forecasting ≠ climate-change analysis.** Predicting tomorrow's temperature is a *weather* task (days).
> Climate change is the long-term (decades) shift in the statistics of weather. The website shows both, but keeps them separate:
> the ML model forecasts weather; the NOAA CO₂/CH₄/N₂O and NASA GISTEMP pages show long-term climate evidence.

### How to run
1. Open this file in Google Colab → **Runtime → Run all** (takes roughly 10–25 minutes, mostly API downloads and model tuning).
2. The last cell downloads `climatesense_artifacts.zip`. Unzip it into the project root so that `backend/models/` and `data/` are filled.
3. The notebook needs internet access (Colab has it) — it calls the public Open-Meteo API, which needs no key.
''')

md(r'''## Section 1 — Environment setup
We import the libraries and fix random seeds so that results are **reproducible**: running the notebook twice on the same data gives the same models.''')

code(r'''
import importlib, subprocess, sys

def ensure(import_name, pip_name=None):
    """Import a package; pip-install it first if it is missing."""
    try:
        return importlib.import_module(import_name)
    except ImportError:
        print(f"Installing {pip_name or import_name} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pip_name or import_name], check=False)
        return importlib.import_module(import_name)

for imp, pip in [("pandas", None), ("numpy", None), ("matplotlib", None), ("seaborn", None),
                 ("sklearn", "scikit-learn"), ("requests", None), ("joblib", None)]:
    ensure(imp, pip)
try:
    shap = ensure("shap")
    SHAP_OK = True
except Exception as exc:          # SHAP is optional: the notebook falls back gracefully
    SHAP_OK = False
    print("SHAP could not be imported -> SHAP cells will use the built-in explainer:", exc)

import os, json, time, random, hashlib, platform, warnings, zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests, joblib, sklearn
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

SEED = 42                                   # one seed used everywhere
random.seed(SEED); np.random.seed(SEED); os.environ["PYTHONHASHSEED"] = str(SEED)

ROOT = Path("climatesense_output")          # everything we create lives here
RAW_DIR, PROC_DIR = ROOT / "data" / "raw", ROOT / "data" / "processed"
MODEL_DIR = ROOT / "backend" / "models"     # <- the folder the FastAPI backend reads
FIG_DIR = MODEL_DIR / "figures"
for d in (RAW_DIR, PROC_DIR, MODEL_DIR, FIG_DIR):
    d.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"figure.dpi": 110, "axes.titleweight": "bold"})

print("python", platform.python_version(), "| pandas", pd.__version__, "| numpy", np.__version__,
      "| scikit-learn", sklearn.__version__, "| SHAP", shap.__version__ if SHAP_OK else "n/a")
''')

md(r'''### 1.1 Shared feature-engineering code
**Why this matters:** a very common bug in ML projects is *train/serve skew* — the features computed for training differ slightly from those computed in the live app, so the model silently gets wrong inputs.
To make that impossible, the notebook writes out the **exact same Python files** that the backend imports (`feature_engineering.py`, `explain_core.py`). Training and live inference therefore run identical code.''')
code("FE_SOURCE = r'''\n@@FE_SOURCE@@\n'''\nEXPLAIN_SOURCE = r'''\n@@EXPLAIN_SOURCE@@\n'''\n\nPath('feature_engineering.py').write_text(FE_SOURCE.lstrip('\\n'), encoding='utf-8')\nPath('explain_core.py').write_text(EXPLAIN_SOURCE.lstrip('\\n'), encoding='utf-8')\nif str(Path.cwd()) not in sys.path:\n    sys.path.insert(0, str(Path.cwd()))\nimport feature_engineering as fe\nimport explain_core\nimportlib.reload(fe)\n\nFE_SHA256 = hashlib.sha256(Path('feature_engineering.py').read_text(encoding='utf-8').replace('\\r\\n', '\\n').encode()).hexdigest()\nprint('feature module version:', fe.FEATURE_MODULE_VERSION, '| sha256:', FE_SHA256[:16], '...')\nprint('Cities       :', list(fe.CITIES))\nprint('Features (%d):' % len(fe.FEATURES), fe.FEATURES)\nprint('Target       :', fe.TARGET, '(maximum temperature of the NEXT day)')")

md(r'''## Section 2 — Data collection (real data only)

### Data product used for training
**Open-Meteo Historical Forecast API** (`historical-forecast-api.open-meteo.com`). It stores *archived weather-model forecasts* (roughly from 2022 onward), stitched together from the first hours of successive model runs.
This is deliberate: the **live website uses the Open-Meteo Forecast API**, i.e. the same family of weather-model products, so the training inputs resemble the live inputs as closely as possible.

> ⚠️ **Honest limitation:** these are *model-derived* values, not readings from a station thermometer. The "target" we predict is therefore the model-estimated maximum temperature, not an official IMD station observation.

For every city we download **hourly** values of: `temperature_2m, relative_humidity_2m, precipitation, wind_speed_10m, surface_pressure, cloud_cover, shortwave_radiation` and aggregate them into daily records with the shared function `fe.hourly_to_daily` (so training and live aggregation are identical).''')

code(r'''
HF_URL   = "https://historical-forecast-api.open-meteo.com/v1/forecast"   # archived NWP forecasts
ERA5_URL = "https://archive-api.open-meteo.com/v1/archive"                # ERA5 / ERA5-Land reanalysis

TRAIN_START = date(2022, 1, 1)                    # archive begins around 2022
TRAIN_END   = date.today() - timedelta(days=2)    # latest days may still be incomplete, so stop 2 days back
RETRIEVED_AT = datetime.now(timezone.utc)

class ApiError(RuntimeError):
    pass

def get_json(url, params, retries=6):
    """GET with retries/back-off. Raises ApiError - we never continue with partial or made-up data."""
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=120)
            if r.status_code == 200:
                js = r.json()
                if isinstance(js, dict) and js.get("error"):
                    raise ApiError(js.get("reason", "API reported an error"))
                return js
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code == 429:
                time.sleep(min(90, 15 * (attempt + 1)))       # rate limited -> wait
            elif r.status_code >= 500:
                time.sleep(4 * (attempt + 1))
            else:
                break                                          # 4xx = our request is wrong; retrying will not help
        except (requests.RequestException, ValueError) as exc:
            last = str(exc)
            time.sleep(4 * (attempt + 1))
    raise ApiError(f"request failed: {last}")

def year_chunks(start, end):
    cur = start
    while cur <= end:
        stop = min(date(cur.year, 12, 31), end)
        yield cur, stop
        cur = stop + timedelta(days=1)

def fetch_city_hourly(city):
    c = fe.CITIES[city]
    parts, units, grid = [], None, None
    for a, b in year_chunks(TRAIN_START, TRAIN_END):
        js = get_json(HF_URL, dict(
            latitude=c["lat"], longitude=c["lon"], start_date=a.isoformat(), end_date=b.isoformat(),
            hourly=",".join(fe.MODEL_HOURLY_VARIABLES), timezone=fe.TIMEZONE,
            temperature_unit="celsius", wind_speed_unit="kmh", precipitation_unit="mm"))
        df = pd.DataFrame(js["hourly"])
        units = units or js.get("hourly_units")
        grid = grid or {"grid_latitude": js.get("latitude"), "grid_longitude": js.get("longitude"),
                        "elevation_m": js.get("elevation")}
        parts.append(df)
        time.sleep(1.0)                                        # be polite to the free API
    out = pd.concat(parts, ignore_index=True)
    out.insert(0, "city", city)
    return out, units, grid

hourly_parts, units_by_city, grid_by_city = [], {}, {}
for city in fe.CITIES:
    t0 = time.time()
    df, units, grid = fetch_city_hourly(city)
    problems = fe.validate_units(units)
    if problems:
        raise ApiError(f"{city}: unexpected units -> {problems}")        # stop instead of mixing units
    hourly_parts.append(df); units_by_city[city] = units; grid_by_city[city] = grid
    print(f"{city:<10} {len(df):>7,} hourly rows | grid cell {grid['grid_latitude']:.3f},{grid['grid_longitude']:.3f} "
          f"| elevation {grid['elevation_m']} m | {time.time() - t0:.0f}s")

hourly_raw = pd.concat(hourly_parts, ignore_index=True)
hourly_raw.to_csv(RAW_DIR / "hourly_raw.csv.gz", index=False)           # raw dataset saved as CSV (gzip)
print("\nTotal hourly rows:", f"{len(hourly_raw):,}", "| saved ->", RAW_DIR / "hourly_raw.csv.gz")
''')

code(r'''
# Coverage report: what period does each city REALLY cover (null rows are not counted as data)?
hourly_raw["time"] = pd.to_datetime(hourly_raw["time"])
valid = hourly_raw.dropna(subset=["temperature_2m"])
coverage = valid.groupby("city").agg(first_valid=("time", "min"), last_valid=("time", "max"), valid_hours=("time", "count"))
coverage["requested_hours"] = (pd.Timestamp(TRAIN_END) - pd.Timestamp(TRAIN_START)).days * 24 + 24
coverage["coverage_pct"] = (100 * coverage["valid_hours"] / coverage["requested_hours"]).round(1)
display(coverage)

OBS_START, OBS_END = valid["time"].min().date(), valid["time"].max().date()
print(f"Observation period actually available: {OBS_START} -> {OBS_END}")
''')

md(r'''### 2.1 Save the dataset metadata
A dataset without documentation is hard to trust. We store *where* the data came from, *when* it was downloaded, *what period* it covers, the *units*, the *record count* and the *cities*.''')
code(r'''
dataset_meta = {
    "name": "ClimateSense AI training dataset (hourly, raw)",
    "source": "Open-Meteo Historical Forecast API (archived weather-model forecasts)",
    "source_url": HF_URL,
    "documentation": "https://open-meteo.com/en/docs/historical-forecast-api",
    "license": "CC BY 4.0 - Open-Meteo.com (weather data); free tier for non-commercial use",
    "retrieval_date_utc": RETRIEVED_AT.isoformat(timespec="seconds"),
    "requested_period": f"{TRAIN_START} to {TRAIN_END}",
    "observation_period": f"{OBS_START} to {OBS_END}",
    "timezone": fe.TIMEZONE,
    "cities": {c: {**fe.CITIES[c], **grid_by_city[c]} for c in fe.CITIES},
    "variables": fe.MODEL_HOURLY_VARIABLES,
    "units": units_by_city[next(iter(fe.CITIES))],
    "hourly_records": int(len(hourly_raw)),
    "records_per_city": hourly_raw.groupby("city").size().to_dict(),
    "nature_of_values": "model-derived (archived NWP forecasts), not station observations",
}
(RAW_DIR / "dataset_metadata.json").write_text(json.dumps(dataset_meta, indent=2, ensure_ascii=False))
print(json.dumps({k: dataset_meta[k] for k in ["source", "retrieval_date_utc", "observation_period", "hourly_records", "units"]},
                 indent=2, ensure_ascii=False))
''')

md(r'''## Section 3 — Data preprocessing
Steps (all are *inspected and reported*, nothing is silently changed):
1. **Duplicate removal** — the same `(city, time)` must appear once.
2. **Missing-value analysis** — we look at nulls before deciding anything; days with too few hours are *dropped*, never filled with invented numbers.
3. **Date parsing** and **unit validation**.
4. **Outlier inspection** — we *look* for strange values but **do not remove genuine extreme-heat events**: heatwaves are exactly what this project is about.
5. **Feature engineering** with the shared module — using only information available at the prediction cutoff.''')

code(r'''
# 3.1 Duplicates + date parsing
n0 = len(hourly_raw)
hourly = hourly_raw.drop_duplicates(subset=["city", "time"]).copy()
hourly["time"] = pd.to_datetime(hourly["time"], errors="raise")
print(f"Duplicate hourly rows removed: {n0 - len(hourly)}")

# 3.2 Missing-value analysis (percent of null hourly values)
miss = hourly.groupby("city")[fe.MODEL_HOURLY_VARIABLES].apply(lambda g: g.isna().mean() * 100).round(3)
print("\nMissing hourly values (%):")
display(miss)

# 3.3 Unit / plausibility validation (physical ranges for India; counts of values outside)
plausible = {"temperature_2m": (-5, 52), "relative_humidity_2m": (0, 100), "precipitation": (0, 200),
             "wind_speed_10m": (0, 250), "surface_pressure": (800, 1100), "cloud_cover": (0, 100),
             "shortwave_radiation": (0, 1500)}
rows = []
for var, (lo, hi) in plausible.items():
    s = hourly[var].dropna()
    rows.append({"variable": var, "unit": fe.EXPECTED_UNITS[var], "min": s.min(), "max": s.max(),
                 "plausible_range": f"{lo}..{hi}", "outside_range": int(((s < lo) | (s > hi)).sum())})
display(pd.DataFrame(rows))
''')

code(r'''
# 3.4 Aggregate to daily records with the SHARED function (days with < 22 valid hours are dropped, never filled)
daily_parts = []
for city, g in hourly.groupby("city"):
    d = fe.hourly_to_daily(g.drop(columns="city"))
    d.insert(0, "city", city)
    daily_parts.append(d)
daily = pd.concat(daily_parts, ignore_index=True)

expected_days = (pd.Timestamp(OBS_END) - pd.Timestamp(OBS_START)).days + 1
summary = daily.groupby("city").agg(days=("date", "count"), first=("date", "min"), last=("date", "max"))
summary["days_missing_or_incomplete"] = expected_days - summary["days"]
display(summary)
daily.to_csv(PROC_DIR / "daily_aggregated.csv", index=False)

# 3.5 Outlier inspection: robust z-score of daily max temperature vs the city's own month median.
daily["month"] = daily["date"].dt.month
med = daily.groupby(["city", "month"])["tmax"].transform("median")
mad = (daily["tmax"] - med).abs().groupby([daily["city"], daily["month"]]).transform("median").clip(lower=0.3)
daily["robust_z"] = 0.6745 * (daily["tmax"] - med) / mad
flag = daily[daily["robust_z"].abs() > 3.5]
print(f"\nDays flagged by the robust z-score (|z|>3.5): {len(flag)} of {len(daily)}  -> INSPECTED, NOT REMOVED")
display(flag.sort_values("tmax", ascending=False).head(10)[["city", "date", "tmax", "tmin", "robust_z"]])
print("Hottest days in the dataset (genuine extremes are kept):")
display(daily.sort_values("tmax", ascending=False).head(5)[["city", "date", "tmax"]])
daily = daily.drop(columns=["month", "robust_z"])
''')

code(r'''
# 3.6 Feature engineering (target = NEXT day's maximum temperature; features use days <= cutoff only)
frames = []
for city, g in daily.groupby("city"):
    c = fe.CITIES[city]
    ff = fe.make_feature_frame(g.drop(columns="city"), c["lat"], c["lon"])
    ff.insert(0, "city", city)
    frames.append(ff)
features_all = pd.concat(frames, ignore_index=True)

model_df = features_all.dropna(subset=fe.FEATURES + [fe.TARGET]).reset_index(drop=True)
print(f"Rows before dropping incomplete windows: {len(features_all):,}")
print(f"Rows usable for modelling              : {len(model_df):,}  "
      f"(dropped {len(features_all) - len(model_df)}: first 6 days per city lack a 7-day window, last day lacks a target)")

# Hard safety checks: the target must never be among the features, and it must be tomorrow's tmax.
assert fe.TARGET not in fe.FEATURES
check = model_df.merge(daily[["city", "date", "tmax"]].rename(columns={"date": "target_date", "tmax": "tmax_check"}),
                       on=["city", "target_date"])
assert np.allclose(check[fe.TARGET], check["tmax_check"]), "target is not the next-day maximum!"
print("✔ Leakage check passed: target == tmax of the following day; no forward-looking feature.")

model_df.to_csv(PROC_DIR / "model_dataset.csv", index=False)
print("\nDescriptive statistics:")
display(model_df[fe.FEATURES + [fe.TARGET]].describe().T.round(3))
''')

code(r'''
# 3.7 Update the dataset metadata with the daily/model row counts
dataset_meta.update({
    "daily_records": int(len(daily)), "model_rows": int(len(model_df)),
    "model_rows_per_city": model_df.groupby("city").size().to_dict(),
    "first_model_date": str(model_df["date"].min().date()), "last_model_date": str(model_df["date"].max().date()),
    "daily_aggregation": {"day": "local calendar day (Asia/Kolkata)", "min_valid_hours": 22,
                          "tmax/tmin": "max/min of hourly temperature_2m", "precipitation": "sum of hourly values",
                          "humidity/wind/pressure/cloud": "mean of hourly values",
                          "solar": "sum of hourly shortwave radiation converted to MJ/m2"},
    "omitted_features": ["Dew point and apparent temperature were not used: not needed for the minimum feature set."],
})
(RAW_DIR / "dataset_metadata.json").write_text(json.dumps(dataset_meta, indent=2, ensure_ascii=False))
print("metadata updated:", RAW_DIR / "dataset_metadata.json")
''')
