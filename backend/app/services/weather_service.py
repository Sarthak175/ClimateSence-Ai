"""Open-Meteo live weather retrieval and shaping."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd

from app.config import settings
from app.ml import feature_engineering as fe
from app.utils.cache import cached_call

HOURLY_VARS = [*fe.MODEL_HOURLY_VARIABLES, "apparent_temperature"]
CURRENT_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation",
    "wind_speed_10m", "surface_pressure", "cloud_cover", "shortwave_radiation",
]
DAILY_VARS = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "wind_speed_10m_max"]
PAST_DAYS = 10
FORECAST_DAYS = 7

SOURCE = {
    "name": "Open-Meteo Forecast API",
    "url": "https://open-meteo.com/en/docs",
    "license": "CC BY 4.0 (non-commercial free tier)",
}
CURRENT_NOTE = (
    "Open-Meteo 'current' values are model-derived (weather-model analysis blended with "
    "available observations). They are NOT readings from a single weather-station instrument."
)


class UpstreamError(RuntimeError):
    def __init__(self, source: str, message: str):
        super().__init__(message)
        self.source = source
        self.message = message


USER_AGENT = "ClimateSenseAI/1.0 (academic project; +https://open-meteo.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,text/plain,*/*"}


def http_get_json(url: str, params: dict) -> dict:
    """GET with a couple of retries; raises UpstreamError on failure."""
    last: Exception | None = None
    for attempt in range(settings.upstream_retries + 1):
        try:
            with httpx.Client(timeout=settings.request_timeout_s, headers=HEADERS, follow_redirects=True) as client:
                r = client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except (httpx.HTTPError, ValueError) as exc:
            last = exc
            time.sleep(0.5 * (attempt + 1))
    raise UpstreamError("Open-Meteo", f"Open-Meteo request failed: {last}")


def _base_params(lat: float, lon: float) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "timezone": fe.TIMEZONE,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }


def city_params(city: str) -> dict:
    c = fe.CITIES[city]
    return _base_params(c["lat"], c["lon"]) | {
        "current": ",".join(CURRENT_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "daily": ",".join(DAILY_VARS),
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
    }


def request_url(city: str) -> str:
    """The exact public URL used to fetch this city's live data (no secrets involved)."""
    return str(httpx.URL(settings.open_meteo_forecast_url).copy_merge_params(city_params(city)))


def fetch_city_raw(city: str) -> dict:
    params = city_params(city)
    data = http_get_json(settings.open_meteo_forecast_url, params)
    data["_fetched_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return data


def get_city_raw(city: str) -> tuple[dict, dict]:
    return cached_call(f"raw:{city}", settings.live_cache_ttl_s, lambda: fetch_city_raw(city),
                       stale_ok=settings.stale_if_error_s)


def hourly_frame(raw: dict) -> pd.DataFrame:
    h = raw.get("hourly") or {}
    if "time" not in h:
        raise UpstreamError("Open-Meteo", "response has no hourly data")
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"])
    return df


def daily_frame_from_hourly(raw: dict) -> pd.DataFrame:
    """Daily records computed with the SAME aggregation used in training."""
    problems = fe.validate_units(raw.get("hourly_units"))
    if problems:
        raise UpstreamError("Open-Meteo", "unexpected units from API: " + "; ".join(problems))
    return fe.hourly_to_daily(hourly_frame(raw), min_hours=24)


def local_now(raw: dict) -> pd.Timestamp:
    offset = int(raw.get("utc_offset_seconds", 19800))
    return pd.Timestamp(datetime.now(timezone.utc)).tz_convert(None) + pd.Timedelta(seconds=offset)


def _r(v: Any, nd: int = 1):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else round(float(v), nd)


def live_payload(city: str) -> dict:
    raw, meta = get_city_raw(city)
    now_local = local_now(raw)
    hf = hourly_frame(raw)
    cur = raw.get("current") or {}
    cur_units = raw.get("current_units") or {}
    daily = raw.get("daily") or {}
    today_str = now_local.strftime("%Y-%m-%d")

    d_dates = daily.get("time", [])
    daily_rows = []
    for i, dt in enumerate(d_dates):
        daily_rows.append({
            "date": dt,
            "tmax_c": _r(daily["temperature_2m_max"][i]),
            "tmin_c": _r(daily["temperature_2m_min"][i]),
            "precip_mm": _r(daily["precipitation_sum"][i]),
            "wind_max_kmh": _r(daily["wind_speed_10m_max"][i]),
            "is_forecast": dt > today_str,
            "is_today": dt == today_str,
        })
    today = next((r for r in daily_rows if r["is_today"]), None)

    # hourly: last 24 h + next 48 h around "now"
    lo, hi = now_local - pd.Timedelta(hours=24), now_local + pd.Timedelta(hours=48)
    window = hf[(hf["time"] >= lo) & (hf["time"] <= hi)]
    hourly_rows = [{
        "time": t.strftime("%Y-%m-%dT%H:%M"),
        "temp_c": _r(r.temperature_2m), "apparent_c": _r(r.apparent_temperature),
        "humidity_pct": _r(r.relative_humidity_2m, 0), "precip_mm": _r(r.precipitation),
        "wind_kmh": _r(r.wind_speed_10m), "pressure_hpa": _r(r.surface_pressure),
        "cloud_pct": _r(r.cloud_cover, 0), "solar_wm2": _r(r.shortwave_radiation, 0),
        "is_forecast": bool(t > now_local),
    } for t, r in zip(window["time"], window.itertuples(index=False))]

    return {
        "city": city,
        "coordinates": fe.CITIES[city],
        "source": {**SOURCE, "request_url": request_url(city),
                   "refresh": f"server cache {settings.live_cache_ttl_s} s; website polls every 5 min"},
        "note": CURRENT_NOTE,
        "timestamps": {
            "api_current_time_local": cur.get("time"),
            "api_interval_s": cur.get("interval"),
            "fetched_at_utc": raw.get("_fetched_at_utc"),
            "timezone": raw.get("timezone"),
            "utc_offset_seconds": raw.get("utc_offset_seconds"),
            "api_generation_ms": raw.get("generationtime_ms"),
        },
        "cache": meta,
        "current": {
            "temperature_c": _r(cur.get("temperature_2m")),
            "apparent_c": _r(cur.get("apparent_temperature")),
            "humidity_pct": _r(cur.get("relative_humidity_2m"), 0),
            "precipitation_mm": _r(cur.get("precipitation")),
            "wind_kmh": _r(cur.get("wind_speed_10m")),
            "pressure_hpa": _r(cur.get("surface_pressure")),
            "cloud_pct": _r(cur.get("cloud_cover"), 0),
            "solar_wm2": _r(cur.get("shortwave_radiation"), 0),
            "units": cur_units,
        },
        "today": today,
        "daily": daily_rows,
        "hourly": hourly_rows,
    }


def compare_cities() -> dict:
    """Current + 7-day max for all cities with one multi-location request."""
    def fetch():
        names = list(fe.CITIES)
        params = {
            "latitude": ",".join(str(fe.CITIES[n]["lat"]) for n in names),
            "longitude": ",".join(str(fe.CITIES[n]["lon"]) for n in names),
            "timezone": fe.TIMEZONE,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "past_days": 3,
            "forecast_days": FORECAST_DAYS,
        }
        data = http_get_json(settings.open_meteo_forecast_url, params)
        if isinstance(data, dict):
            data = [data]
        if len(data) != len(names):
            raise UpstreamError("Open-Meteo", "multi-location response size mismatch")
        out = []
        for n, d in zip(names, data):
            out.append({
                "city": n,
                "current": {
                    "temperature_c": _r(d["current"].get("temperature_2m")),
                    "apparent_c": _r(d["current"].get("apparent_temperature")),
                    "humidity_pct": _r(d["current"].get("relative_humidity_2m"), 0),
                    "wind_kmh": _r(d["current"].get("wind_speed_10m")),
                    "time": d["current"].get("time"),
                },
                "daily": [{
                    "date": dt, "tmax_c": _r(d["daily"]["temperature_2m_max"][i]),
                    "tmin_c": _r(d["daily"]["temperature_2m_min"][i]),
                    "precip_mm": _r(d["daily"]["precipitation_sum"][i]),
                } for i, dt in enumerate(d["daily"]["time"])],
            })
        return {"cities": out, "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    value, meta = cached_call("compare", settings.live_cache_ttl_s, fetch,
                              stale_ok=settings.stale_if_error_s)
    return {**value, "source": SOURCE, "note": CURRENT_NOTE, "cache": meta}
