"""Central configuration, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _csv(name: str, default: str) -> list[str]:
    return [p.strip() for p in os.getenv(name, default).split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "ClimateSense AI API"
    app_version: str = "1.0.0"

    # --- CORS -------------------------------------------------------------
    cors_origins: list[str] = field(default_factory=lambda: _csv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    # optional regex, e.g. https://.*\.vercel\.app  (allows Vercel preview URLs)
    cors_origin_regex: str | None = os.getenv("CORS_ORIGIN_REGEX") or None

    # --- Artifacts --------------------------------------------------------
    model_dir: Path = Path(os.getenv("MODEL_DIR", str(BACKEND_DIR / "models")))

    # --- Upstream data sources -------------------------------------------
    open_meteo_forecast_url: str = os.getenv(
        "OPEN_METEO_FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
    request_timeout_s: float = float(os.getenv("REQUEST_TIMEOUT_S", "20"))
    upstream_retries: int = int(os.getenv("UPSTREAM_RETRIES", "2"))

    # --- Caching (seconds) ------------------------------------------------
    live_cache_ttl_s: int = int(os.getenv("LIVE_CACHE_TTL_S", "300"))      # weather: 5 min
    climate_cache_ttl_s: int = int(os.getenv("CLIMATE_CACHE_TTL_S", "21600"))  # NOAA/NASA: 6 h
    stale_if_error_s: int = int(os.getenv("STALE_IF_ERROR_S", "86400"))

    # --- Sensors (ESP32) --------------------------------------------------
    device_token: str = os.getenv("DEVICE_TOKEN", "")
    sensor_store_path: Path = Path(os.getenv(
        "SENSOR_STORE_PATH", str(BACKEND_DIR / "data" / "sensor_readings.json")))
    sensor_max_readings: int = int(os.getenv("SENSOR_MAX_READINGS", "2000"))

    # --- Inference --------------------------------------------------------
    shap_permutations: int = int(os.getenv("SHAP_PERMUTATIONS", "120"))


settings = Settings()
