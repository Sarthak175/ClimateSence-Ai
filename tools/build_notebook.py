"""Builds notebooks/ClimateSense_AI_ML_Training.ipynb from the cell definition files.

Run:  python tools/build_notebook.py
The shared modules (feature_engineering.py, explain_core.py) are embedded verbatim so the
notebook and the backend always use identical code.
"""
import json
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import nb_part1, nb_part2, nb_part3  # noqa: E402

FE = (ROOT / "backend/app/ml/feature_engineering.py").read_text(encoding="utf-8")
EX = (ROOT / "backend/app/ml/explain_core.py").read_text(encoding="utf-8")
assert "'''" not in FE and "'''" not in EX, "shared modules must not contain triple single quotes"


def build() -> Path:
    nb = nbf.v4.new_notebook()
    cells = []
    for part in (nb_part1, nb_part2, nb_part3):
        for kind, text in part.CELLS:
            text = text.replace("@@FE_SOURCE@@", FE.strip("\n")).replace("@@EXPLAIN_SOURCE@@", EX.strip("\n"))
            cells.append(nbf.v4.new_markdown_cell(text) if kind == "md" else nbf.v4.new_code_cell(text))
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
        "colab": {"name": "ClimateSense_AI_ML_Training.ipynb", "provenance": []},
    }
    out = ROOT / "notebooks" / "ClimateSense_AI_ML_Training.ipynb"
    nbf.write(nb, out)
    return out


if __name__ == "__main__":
    p = build()
    print("wrote", p, p.stat().st_size // 1024, "KB")
