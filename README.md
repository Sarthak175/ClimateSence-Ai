# 🌍 ClimateSense AI

**Live Urban Heat-Island Monitoring, Climate Intelligence and ML-Based Temperature Prediction**
Third-year ML project · *Global Warming and Climate Change* · topic *Urban Heat-Island Reduction*

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR-USER/climatesense-ai/blob/main/notebooks/ClimateSense_AI_ML_Training.ipynb)

An actual working ML application - not a static weather page:

| Layer | What it does |
|---|---|
| **Colab notebook** | downloads real Open-Meteo data, trains **Linear Regression, SVR (RBF), Random Forest** (+ persistence baseline) to predict *tomorrow's maximum temperature*, evaluates with **MAE / MSE / R²**, explains with RF importance, permutation importance and SHAP, builds 1991-2020 ERA5-Land normals, exports the model |
| **FastAPI backend** | live Open-Meteo weather, predictions from the *exported* model (503 if it is missing - never invented), local explanations, NOAA CO₂/CH₄/N₂O, NASA GISTEMP, ESP32 sensor endpoints, caching, validation, CORS |
| **React dashboard** | 8 pages: Dashboard · Live Monitoring · AI Predictions · Model Lab · Explainable AI · Climate Evidence · Urban Cooling · Prototype Lab |
| **Optional ESP32 prototype** | two DS18B20 sensors (dark vs reflective roof) → live chart on the website |

> **Weather ≠ climate.** The daily regression model forecasts *weather*. It does not prove greenhouse-gas causation. Long-term climate evidence (NOAA, NASA) is shown separately.

## Easiest: run everything on localhost (one command)
Needs Python 3.10+, Node 18+ and internet (the first run trains the model on real Open-Meteo data, ~10-25 min; later runs start in seconds).

```bash
./run_local.sh        # Linux / macOS
run_local.bat         # Windows
```
Then open **http://localhost:5173** (API docs: http://localhost:8000/docs). To retrain later, delete `backend/models/best_model.joblib` and run the script again. Nothing is deployed - everything stays on your machine.

## Trained model (already included)
`backend/models/` ships a model trained on **real Open-Meteo data** (retrieved 2026-11-12; 6 cities, 2022-01-01 → 2026-11-10). Real metrics: see the Model Lab page, `backend/models/model_metrics.json` and `docs/REPORT.md`. The API's `/api/model-quality` endpoint re-checks the metrics against the readiness policy every time. To retrain on fresh data, run `python tools/run_local_training.py` (or the Colab notebook) and restart the backend - scikit-learn must stay at the version in `RUNTIME_VERSIONS.txt`.

## Quick start
```bash
# Backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && uvicorn app.main:app --reload      # http://localhost:8000/docs
# Frontend (new terminal)
cd frontend && npm install && cp .env.example .env.local && npm run dev  # http://localhost:5173
```
Full instructions: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** (GitHub → Render → Vercel), **[docs/PUBLISHING.md](docs/PUBLISHING.md)** (public Colab/website), **[docs/API.md](docs/API.md)**, **[docs/PROTOTYPE.md](docs/PROTOTYPE.md)** (ESP32), **[docs/REPORT_TEMPLATE.md](docs/REPORT_TEMPLATE.md)** (+ `python tools/generate_report.py` fills in real results).

## Repository structure
```
climatesense-ai/
├── notebooks/ClimateSense_AI_ML_Training.ipynb   # 10 numbered sections, built by tools/build_notebook.py
├── backend/
│   ├── app/
│   │   ├── main.py  config.py
│   │   ├── routes/    weather · predictions · models · climate · explainability · sensors
│   │   ├── services/  weather · climate · prediction · explanation · sensor
│   │   ├── ml/        feature_engineering.py (shared with the notebook!) · explain_core.py · model_loader.py
│   │   └── utils/     cache.py · validators.py
│   ├── models/        <- trained artifacts go here
│   ├── tests/         pytest (leakage, API, parsing, auth)
│   ├── requirements.txt  Dockerfile
├── frontend/          React + Vite + React Router + Recharts + Lucide + Axios, plain CSS
├── hardware/esp32/    Arduino sketch for the roof-temperature node
├── docs/              deployment, API, prototype, report template, architecture.svg
├── tools/             build_notebook.py · generate_report.py · offline test harnesses
├── render.yaml  .env.example  .gitignore
└── data/              raw dataset + metadata (created by the notebook)
```

## How the "no train/serve skew" guarantee works
`backend/app/ml/feature_engineering.py` is embedded verbatim into the notebook (`tools/build_notebook.py`) **and** imported by the API. Same hourly→daily aggregation, same 18 features, same units check. `feature_schema.json` stores the feature list and module version; the API refuses to serve a model whose schema does not match. Unit tests prove that changing *future* data cannot change today's features (no target leakage).

## Data sources (all real, all attributed on the site)
Open-Meteo Forecast API · Open-Meteo Historical Forecast API · Open-Meteo Historical Weather API (ERA5-Land) · NOAA GML (CO₂, CH₄, N₂O) · NASA GISS GISTEMP v4. NOAA/NASA series are **monthly** products - the site labels them as such and never calls them "live measurements". Open-Meteo "current" values are **model-derived**, not station readings.

## Known limitations (honest)
~4 years of archived model data (not station observations); six cities; heat categories are project-defined (not IMD warnings); training target is the Open-Meteo archive, climate normals are ERA5-Land (a per-city product offset is measured and applied, see notebook §9); free-tier APIs are rate-limited; Render free tier sleeps and has ephemeral disk.

Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0). Academic project - not an official warning service.


## Run on Windows (one command)

Extract the zip completely, open PowerShell in the `climatesense-ai` folder (the one with `backend` and `frontend` inside) and run:

```powershell
.\run_local.bat
```

It creates a fresh backend environment, installs packages, starts the backend (port 8000) and the frontend (port 5173) and opens the browser. Keep both windows open. Check http://localhost:8000/api/health for `"loaded": true`.

## Manual entry (what-if) prediction

Open **AI Predictions -> Manual entry (what-if)**. Type the weather of a cutoff day (13 values: temperatures,
humidity, cloud, pressure, wind, solar radiation, rain) and press **Predict**. The same trained model returns the
next-day maximum temperature, the 90 % interval, the heat category and a per-feature explanation.

* "Fill with live values" loads today's real Open-Meteo inputs for the selected city so you can edit them.
* "Fill training medians" is a neutral starting point (labelled as not a real observation).
* Nothing is guessed: every field is required; impossible values (humidity 140 %, min > max, ...) are rejected
  with a clear message; values outside the training range produce a warning.
* The 3-day mean, season terms and latitude/longitude are derived by the same code used in training.
* API: `POST /api/predict/manual`, field list: `GET /api/predict/manual/schema` (see http://localhost:8000/docs).
