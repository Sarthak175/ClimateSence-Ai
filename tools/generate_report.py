"""Fills docs/REPORT.md with the ACTUAL results produced by the Colab notebook.

Usage:  python tools/generate_report.py
Requires backend/models/model_metrics.json + training_metadata.json + feature_importance.json.
Nothing is invented: if an artifact is missing the script stops. Prototype observations are
computed only from real readings in backend/data/sensor_readings.json (if any).
"""
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
M_DIR = ROOT / "backend" / "models"


def load(name):
    p = M_DIR / name
    if not p.exists():
        sys.exit(f"Missing {p}. Run the Colab notebook and copy its artifacts first (see docs/DEPLOYMENT.md).")
    return json.loads(p.read_text())


metrics, meta, imp = load("model_metrics.json"), load("training_metadata.json"), load("feature_importance.json")
best = metrics["best_model"]["name"]
f = lambda v, d=3: f"{v:.{d}f}"
rows = []
for n, m in metrics["models"].items():
    star = " **(selected)**" if n == best else ""
    rows.append(f"| {n}{star} | {f(m['validation']['mae'])} | {f(m['validation']['mse'])} | {f(m['validation']['r2'])} | "
                f"{f(m['test']['mae'])} | {f(m['test']['mse'])} | {f(m['test']['r2'])} |")
b = metrics["baseline_persistence"]
rows.append(f"| Persistence baseline | {f(b['validation']['mae'])} | {f(b['validation']['mse'])} | {f(b['validation']['r2'])} | "
            f"{f(b['test']['mae'])} | {f(b['test']['mse'])} | {f(b['test']['r2'])} |")

perm = sorted(imp["permutation"]["mean"].items(), key=lambda kv: -kv[1])[:3]
labels = imp.get("feature_labels", {})
top = ", ".join(f"{labels.get(k, {}).get('label', k)} (+{v:.2f} °C MAE when shuffled)" for k, v in perm)
imp_t = metrics["improvement_over_persistence_pct"]["test_mae"]
city_mae = metrics["per_city_test_mae"]
worst, bestc = max(city_mae, key=city_mae.get), min(city_mae, key=city_mae.get)
pi = metrics["prediction_interval"]
ds, sp = meta["dataset"], metrics["split"]

obs = [
    f"On the untouched test period the selected model ({best}) reached MAE {f(metrics['best_model']['test']['mae'])} °C, "
    f"MSE {f(metrics['best_model']['test']['mse'])} °C² and R² {f(metrics['best_model']['test']['r2'])}.",
    (f"Its MAE is {abs(imp_t):.1f} % {'lower' if imp_t > 0 else 'HIGHER'} than the persistence baseline ('tomorrow = today')"
     + ("." if imp_t > 0 else " - the machine-learning model did not beat the baseline on the test set.")),
    f"Largest permutation importances: {top}.",
    f"Test MAE is lowest in {bestc} ({f(city_mae[bestc], 2)} °C) and highest in {worst} ({f(city_mae[worst], 2)} °C).",
    f"The empirical 90 % interval ({pi['lower_offset']:+.2f} to {pi['upper_offset']:+.2f} °C) covered {pi['test_coverage'] * 100:.0f} % of test days.",
]
he = metrics.get("heat_event_detection")
if he:
    obs.append(f"Detecting days at or above the 90th percentile: precision {f(he['precision'], 2)}, recall {f(he['recall'], 2)} "
               f"({he['n_actual_events']} events in {he['n_test_days']} test days).")

sensor_p = ROOT / "backend" / "data" / "sensor_readings.json"
if sensor_p.exists() and json.loads(sensor_p.read_text()):
    r = json.loads(sensor_p.read_text())
    d = [x["difference_c"] for x in r]
    proto = (f"{len(r)} real readings were stored from device(s) {sorted({x['device_id'] for x in r})}. Mean dark-roof temperature "
             f"{statistics.mean(x['dark_roof_c'] for x in r):.2f} °C, mean reflective-roof temperature "
             f"{statistics.mean(x['reflective_roof_c'] for x in r):.2f} °C, mean difference {statistics.mean(d):+.2f} °C "
             f"(max {max(d):+.2f} °C). CHECK these are real experiment readings and not test posts before submitting.")
else:
    proto = "No physical-prototype data were collected, so no experimental result is claimed."

tpl = (ROOT / "docs" / "REPORT_TEMPLATE.md").read_text(encoding="utf-8")
out = (tpl.replace("{{DATE}}", date.today().isoformat()).replace("{{PERIOD}}", ds.get("period", "n/a"))
       .replace("{{RETRIEVED}}", ds.get("retrieval_date_utc", "n/a")[:10]).replace("{{ROWS}}", f"{ds.get('model_rows', 0):,}")
       .replace("{{CITIES}}", ", ".join(ds.get("cities", {}))).replace("{{BEST}}", best)
       .replace("{{TABLE}}", "\n".join(rows)).replace("{{OBS}}", "\n".join(f"- {o}" for o in obs)).replace("{{PROTO}}", proto)
       .replace("{{SPLIT}}", f"train {sp['train']['start']}→{sp['train']['end']}, validation {sp['validation']['start']}→{sp['validation']['end']}, "
                             f"test {sp['test']['start']}→{sp['test']['end']}"))
(ROOT / "docs" / "REPORT.md").write_text(out, encoding="utf-8")
print("wrote docs/REPORT.md")
