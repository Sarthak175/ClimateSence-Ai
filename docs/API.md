# ClimateSense AI - API reference

Base URL (local): `http://localhost:8000` · interactive docs: `/docs` (Swagger UI) and `/redoc`.
All JSON. Errors use `{"detail": {"error": "<code>", "message": "..."}}`.

| Status | `error` code | Meaning |
|---|---|---|
| 404 | `unknown_city` | City not in Chennai, Delhi, Mumbai, Bengaluru, Hyderabad, Kolkata |
| 422 | `insufficient_data` / validation | Not enough clean upstream data to build the features, or bad payload |
| 401 | `invalid_device_token` | Wrong / missing `X-Device-Token` on the sensor endpoint |
| 502 | `upstream_unavailable` | Open-Meteo / NOAA / NASA failed and no cached copy exists |
| 503 | `model_unavailable` | Trained artifacts missing or inconsistent (**no prediction is ever invented**) / sensor writes disabled |

## System
### `GET /api/health`
Service status, model state (`model.loaded`, `model.reason`), whether sensor writes are enabled. `?deep=true` additionally probes Open-Meteo, NOAA and NASA reachability.

## Weather
### `GET /api/cities`
Supported cities with coordinates.
### `GET /api/live?city=Chennai`
Current conditions, today's min/max, 14-day daily series (7 past + 7 forecast), hourly series (24 h past + 48 h ahead).
`timestamps.api_current_time_local` is the API's own timestamp; `note` explains that values are model-derived (not station observations). `cache.stale=true` means the upstream failed and the last good copy is served.
### `GET /api/compare`
Current temperature and 10-day daily max/min for all cities (one multi-location request).

## Machine learning
### `GET /api/predict?city=Chennai&basis=today|last_complete`
Next-day maximum temperature.
* `basis=today` (default): cutoff = today → forecast for tomorrow. The remaining hours of *today* come from the weather model; a warning says how many.
* `basis=last_complete`: cutoff = yesterday → prediction for today using only complete past days.

Response (abridged):
```json
{
  "city": "Chennai",
  "model": {"name": "Random Forest", "selected_by": "lowest validation MAE"},
  "prediction": {"predicted_tmax_c": 34.2, "prediction_date": "2026-11-13", "cutoff_date": "2026-11-12",
                 "interval": {"level": 0.9, "lower_c": 32.5, "upper_c": 35.9, "test_coverage": 0.9}},
  "climatology": {"baseline_period": "1991-2020", "seasonal_normal_c": 31.0, "p90_c": 33.0, "p95_c": 33.8, "anomaly_c": 3.2},
  "heat_risk": {"level": 2, "label": "High", "disclaimer": "Project-defined ... NOT official IMD warnings."},
  "reference_nwp_forecast_tmax_c": 33.9,
  "features_used": {"tmax_d0": 33.1, "...": "..."},
  "warnings": []
}
```
(The numbers above only illustrate the structure.)
### `GET /api/predict/all` - the same for every city.
### `GET /api/metrics` - the notebook's `model_metrics.json` (MAE/MSE/R² for train, validation, test; baseline; interval; per-city scores).
### `GET /api/models` - candidate models, tuned hyper-parameters, dataset and normals metadata, feature list.
### `GET /api/explain?city=Chennai`
`global` = importance data saved in training (RF, permutation, SHAP); `local` = contributions (°C) of every feature to *today's* prediction, computed live with permutation-sampling Shapley values against the training-mean baseline; contributions sum to `predicted − base`.

## Climate evidence
### `GET /api/climate-indicators`
NOAA GML global monthly CO₂ (ppm), CH₄ (ppb), N₂O (ppb) and NASA GISTEMP v4 anomalies (°C vs 1951-1980). Each indicator has `latest`, full series, and `source` (page URL, data URL, `source_updated`). Missing GISTEMP months (`***`) are skipped; the incomplete current year is flagged `complete:false` (year-to-date mean). One failing source is reported in `errors` without blanking the others. Cached 6 h.

## Prototype sensors
### `GET /api/sensor/latest?limit=200`
`{"available": false, ...}` if no hardware has ever reported - the website then shows nothing.
### `POST /api/sensor/reading`
Header `X-Device-Token: <DEVICE_TOKEN>`. Body:
```json
{"device_id": "esp32-roof-lab", "dark_roof_c": 41.25, "reflective_roof_c": 36.80,
 "ambient_c": 29.4, "light_on": true, "timestamp": "2026-11-12T10:15:00Z"}
```
`ambient_c`, `light_on`, `timestamp` optional (server time used). Temperatures must lie in the DS18B20 range (−55…125 °C); exactly `85.0` is rejected (the sensor's power-on value).
