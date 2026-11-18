"""ClimateSense AI - FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.ml import feature_engineering as fe
from app.ml.feature_engineering import FeatureError
from app.ml.model_loader import ModelUnavailable, registry
from app.routes import climate, explainability, models, predictions, sensors, weather
from app.services.weather_service import UpstreamError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    registry.load()
    yield


app = FastAPI(
    title=settings.app_name, version=settings.app_version, lifespan=lifespan,
    description="Live urban-heat monitoring, climate indicators and ML next-day temperature prediction. "
                "No prediction is ever returned unless it comes from the trained model.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Device-Token"],
)


@app.exception_handler(RequestValidationError)
async def _invalid(_: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query"))
        msg = str(e.get("msg", "invalid")).removeprefix("Value error, ")
        msgs.append(f"{loc}: {msg}" if loc and loc not in msg else msg)
    return JSONResponse(status_code=422, content={"detail": {
        "error": "invalid_input", "message": "; ".join(msgs) or "Invalid input."}})


@app.exception_handler(UpstreamError)
async def _upstream(_: Request, exc: UpstreamError):
    return JSONResponse(status_code=502, content={"detail": {
        "error": "upstream_unavailable", "source": exc.source, "message": exc.message}})


@app.exception_handler(ModelUnavailable)
async def _model(_: Request, exc: ModelUnavailable):
    return JSONResponse(status_code=503, content={"detail": {"error": "model_unavailable", "message": str(exc)}})


@app.exception_handler(FeatureError)
async def _feature(_: Request, exc: FeatureError):
    return JSONResponse(status_code=422, content={"detail": {
        "error": "insufficient_data", "message": str(exc)}})


@app.get("/api/health", tags=["system"])
def health(deep: bool = False):
    body = {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": {"loaded": registry.loaded, "name": registry.model_name, "reason": registry.reason,
                  "warnings": registry.warnings},
        "sensor_writes_enabled": bool(settings.device_token),
        "cities": list(fe.CITIES),
    }
    if deep:  # lightweight reachability probes of upstream sources
        probes = {}
        for name, url in {
            "open_meteo": "https://api.open-meteo.com/v1/forecast?latitude=13.08&longitude=80.27&current=temperature_2m",
            "noaa_gml": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv",
            "nasa_gistemp": "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv",
        }.items():
            try:
                with httpx.Client(timeout=8, follow_redirects=True) as c:
                    probes[name] = "reachable" if c.head(url).status_code < 500 else "error"
            except httpx.HTTPError:
                probes[name] = "unreachable"
        body["upstream"] = probes
    return body


for r in (weather.router, predictions.router, models.router, climate.router,
          explainability.router, sensors.router):
    app.include_router(r, prefix="/api")


@app.get("/", include_in_schema=False)
def root():
    return {"service": settings.app_name, "docs": "/docs", "health": "/api/health"}
