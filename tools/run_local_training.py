"""Run the Colab notebook locally (real Open-Meteo data) and install the artifacts.

Usage (from repo root, inside the backend venv):  python tools/run_local_training.py
Needs internet. Takes ~10-25 min. Result: backend/models/*, data/*.
"""
import os, shutil, sys, time
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))
import nbformat

nb = nbformat.read(REPO / "notebooks" / "ClimateSense_AI_ML_Training.ipynb", as_version=4)
work = REPO / ".train_work"
shutil.rmtree(work, ignore_errors=True)
work.mkdir()
os.chdir(work)
ns = {"__name__": "__main__",
      "display": lambda x: print(x.to_string()[:1500] if hasattr(x, "to_string") else x)}
t0 = time.time()
for i, c in enumerate(nb.cells):
    if c.cell_type != "code":
        continue
    if c.source.lstrip().startswith("%"):       # skip notebook magics
        continue
    try:
        exec(compile(c.source, f"<notebook cell {i}>", "exec"), ns)
    except Exception:
        print(f"\n!!! Notebook cell {i} failed:\n{c.source[:500]}\n")
        raise
print(f"\nTraining finished in {(time.time() - t0) / 60:.1f} min")

out = work / "climatesense_output"
models_dst, data_dst = REPO / "backend" / "models", REPO / "data"
models_dst.mkdir(exist_ok=True)
for p in (out / "backend" / "models").iterdir():
    shutil.copytree(p, models_dst / p.name, dirs_exist_ok=True) if p.is_dir() else shutil.copy2(p, models_dst / p.name)
shutil.copytree(out / "data", data_dst, dirs_exist_ok=True)
os.chdir(REPO)
shutil.rmtree(work, ignore_errors=True)
print("Artifacts installed in backend/models/ and data/. Next: start backend + frontend.")
