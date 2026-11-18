"""TEST-ONLY harness: executes every code cell of the notebook with requests.get patched to
return SYNTHETIC Open-Meteo-shaped responses. It verifies that the notebook code runs end to end.
Outputs go to a temporary directory and are NEVER copied into the project.

Usage: python tools/test_notebook_offline.py
"""
import json, os, sys, tempfile, types, time
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

import nbformat
import numpy as np
import pandas as pd
import requests
from tests.synthetic import synthetic_hourly, hourly_json, UNITS

nb = nbformat.read(REPO / "notebooks" / "ClimateSense_AI_ML_Training.ipynb", as_version=4)


class FakeResp:
    def __init__(self, js): self._js, self.status_code, self.text = js, 200, "ok"
    def json(self): return self._js


def fake_get(url, params=None, timeout=None, **kw):
    lat, lon = float(params["latitude"]), float(params["longitude"])
    if "historical-forecast-api" in url:
        h = synthetic_hourly(lat, params["start_date"], params["end_date"], seed=5)
        h = h.drop(columns=["apparent_temperature"])
        return FakeResp({"latitude": lat, "longitude": lon, "elevation": 10.0, "hourly_units": UNITS, "hourly": hourly_json(h)})
    if "archive-api" in url:
        h = synthetic_hourly(lat, params["start_date"], params["end_date"], seed=9)
        d = h.assign(date=h.time.dt.strftime("%Y-%m-%d")).groupby("date")["temperature_2m"].max() + 0.7
        return FakeResp({"latitude": lat, "longitude": lon, "elevation": 10.0, "daily_units": {"temperature_2m_max": "°C"},
                         "daily": {"time": d.index.tolist(), "temperature_2m_max": d.round(2).tolist()}})
    raise AssertionError("unexpected URL " + url)


requests.get = fake_get
import time as _t
_t.sleep = lambda *_: None                      # skip politeness delays in the test

work = Path(tempfile.mkdtemp(prefix="nbtest_"))
os.chdir(work)
ns = {"__name__": "__main__", "display": lambda x: print(x if not hasattr(x, "to_string") else x.to_string()[:1500])}
t0 = time.time()
for i, c in enumerate(nb.cells):
    if c.cell_type != "code":
        continue
    src = c.source
    try:
        exec(compile(src, f"<cell {i}>", "exec"), ns)
    except Exception:
        print(f"\n!!!! FAILED in cell {i}:\n{src[:400]}\n")
        raise
print(f"\nALL CELLS EXECUTED in {time.time() - t0:.0f}s. Output dir: {work}")
out = work / "climatesense_output" / "backend" / "models"
print(sorted(p.name for p in out.iterdir()))
print(json.dumps(json.loads((out / "model_metrics.json").read_text())["best_model"], indent=1))
