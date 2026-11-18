"""Loads the artifacts exported by the Colab notebook.

If anything is missing or inconsistent the registry reports `loaded=False` with a
reason - the API then answers 503 instead of ever inventing a prediction.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.config import settings
from app.ml import feature_engineering as fe

log = logging.getLogger("climatesense.model")

REQUIRED_FILES = [
    "best_model.joblib",
    "model_metrics.json",
    "feature_importance.json",
    "feature_schema.json",
    "training_metadata.json",
    "city_climate_normals.csv",
]


class ModelUnavailable(RuntimeError):
    """The trained model / artifacts are not available."""


def _feature_module_hash() -> str:
    src = Path(fe.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


class ModelRegistry:
    def __init__(self, model_dir: Path | None = None) -> None:
        self.model_dir = Path(model_dir or settings.model_dir)
        self.loaded = False
        self.reason: str | None = "not loaded yet"
        self.model: Any = None
        self.metrics: dict = {}
        self.importance: dict = {}
        self.schema: dict = {}
        self.metadata: dict = {}
        self.normals: pd.DataFrame | None = None
        self.warnings: list[str] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def load(self) -> None:
        with self._lock:
            self.loaded, self.reason, self.warnings = False, None, []
            missing = [f for f in REQUIRED_FILES if not (self.model_dir / f).exists()]
            if missing:
                self.reason = (
                    "Model artifacts missing: " + ", ".join(missing) +
                    f". Looked in: {self.model_dir}. The shipped zip contains these files - extract the "
                    "latest climatesense-ai.zip completely and restart the backend from that folder, or run "
                    "`python tools/run_local_training.py` / the Colab notebook to create them."
                )
                log.warning(self.reason)
                return
            try:
                self.schema = json.loads((self.model_dir / "feature_schema.json").read_text())
                self.metrics = json.loads((self.model_dir / "model_metrics.json").read_text())
                self.importance = json.loads((self.model_dir / "feature_importance.json").read_text())
                self.metadata = json.loads((self.model_dir / "training_metadata.json").read_text())
                normals = pd.read_csv(self.model_dir / "city_climate_normals.csv")
                normals["city"] = normals["city"].astype(str)
                self.normals = normals

                if self.schema.get("features") != fe.FEATURES:
                    raise ModelUnavailable(
                        "feature_schema.json does not match feature_engineering.FEATURES - "
                        "model and serving code are out of sync; retrain the model.")
                if self.schema.get("feature_module_version") != fe.FEATURE_MODULE_VERSION:
                    raise ModelUnavailable(
                        f"Feature module version mismatch (model {self.schema.get('feature_module_version')} "
                        f"vs code {fe.FEATURE_MODULE_VERSION}).")
                if self.schema.get("feature_module_sha256") not in (None, _feature_module_hash()):
                    self.warnings.append(
                        "feature_engineering.py differs byte-wise from the version used in training "
                        "(features/version still match).")

                self.model = joblib.load(self.model_dir / "best_model.joblib")
                trained_sk = self.metadata.get("environment", {}).get("scikit_learn")
                import sklearn
                if trained_sk and trained_sk.split(".")[:2] != sklearn.__version__.split(".")[:2]:
                    self.warnings.append(
                        f"scikit-learn version differs (trained {trained_sk}, serving {sklearn.__version__}); "
                        f"pin scikit-learn=={trained_sk} in requirements.txt.")
                self.loaded = True
                log.info("Model loaded: %s", self.model_name)
            except ModelUnavailable as exc:
                self.reason = str(exc)
                log.error(self.reason)
            except Exception as exc:  # corrupt pickle, bad JSON ...
                self.reason = f"Failed to load model artifacts: {exc}"
                log.exception("model load failed")

    # ------------------------------------------------------------------
    @property
    def model_name(self) -> str | None:
        return self.metrics.get("best_model", {}).get("name") if self.metrics else None

    def require(self) -> None:
        if not self.loaded:
            raise ModelUnavailable(self.reason or "model not loaded")

    def normal_for(self, city: str, target_date) -> dict:
        """Seasonal normal / p90 / p95 of daily max temperature for a city and date."""
        self.require()
        doy = int(fe.day_of_year_365([pd.Timestamp(target_date)])[0])
        rows = self.normals[(self.normals["city"] == city) & (self.normals["doy"] == doy)]
        if rows.empty:
            raise ModelUnavailable(f"No climate normal available for {city} (day-of-year {doy}).")
        r = rows.iloc[0]
        return {
            "doy": doy,
            "normal_tmax_c": float(r["normal_tmax"]),
            "p90_tmax_c": float(r["p90_tmax"]),
            "p95_tmax_c": float(r["p95_tmax"]),
            "std_tmax_c": float(r["std_tmax"]),
        }


registry = ModelRegistry()
