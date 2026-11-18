"""TEST-ONLY local server: real FastAPI app + SYNTHETIC upstream responses (no internet needed).

Used to check the UI/API integration offline. Usage:
    python tools/dev_mock_server.py <path-to-models-dir> [port]
Nothing produced here is part of the project's data.
"""
import os, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
os.environ["MODEL_DIR"] = sys.argv[1]
os.environ.setdefault("DEVICE_TOKEN", "dev-token")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:4173,http://localhost:5173")
os.environ.setdefault("SENSOR_STORE_PATH", "/tmp/mock_sensor.json")
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

import numpy as np
import pandas as pd
import uvicorn
from app import main
from app.services import climate_service, weather_service
from tests.synthetic import forecast_response


def fake_get(url, params):
    today = (pd.Timestamp.utcnow().tz_convert(None) + pd.Timedelta(hours=5.5)).normalize()
    if isinstance(params["latitude"], str):
        lats = [float(x) for x in params["latitude"].split(",")]
        lons = [float(x) for x in params["longitude"].split(",")]
        return [forecast_response(a, b, today, 3, 7) for a, b in zip(lats, lons)]
    return forecast_response(params["latitude"], params["longitude"], today)


def noaa(start_year, v0, v1, amp, name):
    rows = ["# SYNTHETIC TEST DATA", f"# File Creation: test {name}", "year,month,decimal,average,average_unc,trend,trend_unc"]
    months = pd.period_range(f"{start_year}-01", "2026-08", freq="M")
    n = len(months)
    for i, p in enumerate(months):
        base = v0 + (v1 - v0) * (i / n) ** 1.2
        rows.append(f"{p.year},{p.month},{p.year + p.month / 12:.3f},{base + amp * np.sin(2 * np.pi * p.month / 12):.2f},0.1,{base:.2f},0.1")
    return "\n".join(rows)


def giss():
    hdr = "Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON"
    rows = ["Land-Ocean: Global Means", hdr]
    for y in range(1880, 2027):
        base = -0.25 + 1.4 * ((y - 1880) / 146) ** 2.2
        if y < 2026:
            vals = [f"{base + 0.1 * np.sin(m):.2f}" for m in range(12)]
            rows.append(f"{y}," + ",".join(vals) + f",{base:.2f}," + ",".join(["0"] * 5))
        else:
            vals = [f"{base + 0.1 * np.sin(m):.2f}" for m in range(8)] + ["***"] * 4
            rows.append(f"{y}," + ",".join(vals) + "," + ",".join(["***"] * 6))
    return "\n".join(rows)


def fake_dl(urls, source):
    u = urls[0]
    if "co2" in u: t = noaa(1979, 336, 425, 3, "co2")
    elif "ch4" in u: t = noaa(1983, 1640, 1935, 8, "ch4")
    elif "n2o" in u: t = noaa(2001, 316, 339, 0.3, "n2o")
    else: t = giss()
    return t, {"data_url": u, "last_modified": "Tue, 03 Nov 2026 10:00:00 GMT"}


weather_service.http_get_json = fake_get
climate_service._download = fake_dl
uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")
