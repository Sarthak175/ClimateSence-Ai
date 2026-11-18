"""Input validation helpers and request models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.ml.feature_engineering import CITIES


def validate_city(city: str) -> str:
    """Return the canonical city name or raise HTTP 404."""
    key = (city or "").strip().lower()
    for name in CITIES:
        if name.lower() == key:
            return name
    raise HTTPException(
        status_code=404,
        detail={"error": "unknown_city", "message": f"City '{city}' is not supported.",
                "supported": list(CITIES)},
    )


DS18B20_MIN_C = -55.0
DS18B20_MAX_C = 125.0


class SensorReading(BaseModel):
    """Payload sent by the ESP32 prototype (two DS18B20 sensors)."""

    device_id: str = Field(default="esp32-roof-lab", min_length=1, max_length=64)
    dark_roof_c: float = Field(description="Conventional dark roof sensor, °C")
    reflective_roof_c: float = Field(description="Reflective / green roof sensor, °C")
    ambient_c: Optional[float] = Field(default=None, description="Optional ambient sensor, °C")
    light_on: Optional[bool] = Field(default=None, description="Is the lamp on?")
    timestamp: Optional[datetime] = Field(
        default=None, description="Optional ISO-8601 time; server time is used if omitted")

    @field_validator("dark_roof_c", "reflective_roof_c", "ambient_c")
    @classmethod
    def _range(cls, v):
        if v is None:
            return v
        if not (DS18B20_MIN_C <= v <= DS18B20_MAX_C):
            raise ValueError(f"temperature {v} outside DS18B20 range {DS18B20_MIN_C}..{DS18B20_MAX_C} °C")
        if v == 85.0:
            raise ValueError("85.0 °C is the DS18B20 power-on default; sensor not read correctly")
        return v


# ---- manual entry (what-if) -------------------------------------------------
# Hard physical limits for a single city-day. Values outside are rejected (422);
# values merely unusual for the training data produce a warning instead.
MANUAL_LIMITS = {
    "tmax_d0": (-10.0, 55.0), "tmin_d0": (-15.0, 45.0), "tmax_d1": (-10.0, 55.0),
    "tmax_d2": (-10.0, 55.0), "tmin_d1": (-15.0, 45.0), "rh_mean_d0": (0.0, 100.0),
    "precip_d0": (0.0, 1000.0), "precip_sum3": (0.0, 2000.0), "wind_mean_d0": (0.0, 200.0),
    "solar_mj_d0": (0.0, 40.0), "pressure_mean_d0": (300.0, 1100.0), "cloud_mean_d0": (0.0, 100.0),
    "tmax_roll7": (-10.0, 55.0),
}


class ManualInput(BaseModel):
    """User-typed weather values for the cutoff day (all fields are required - nothing is guessed).

    `tmax_roll3`, the season terms and latitude/longitude are NOT typed: they are derived
    deterministically from these values, the city and the date by the shared training code.
    """

    city: str = Field(default="Chennai")
    cutoff_date: str = Field(description="Cutoff day (YYYY-MM-DD); the forecast is for the NEXT day")
    tmax_d0: float = Field(description="Max temperature on the cutoff day, °C")
    tmin_d0: float = Field(description="Min temperature on the cutoff day, °C")
    tmax_d1: float = Field(description="Max temperature 1 day before the cutoff day, °C")
    tmax_d2: float = Field(description="Max temperature 2 days before the cutoff day, °C")
    tmin_d1: float = Field(description="Min temperature 1 day before the cutoff day, °C")
    rh_mean_d0: float = Field(description="Mean relative humidity on the cutoff day, %")
    precip_d0: float = Field(description="Rain total on the cutoff day, mm")
    precip_sum3: float = Field(description="Rain total over the last 3 days (cutoff day included), mm")
    wind_mean_d0: float = Field(description="Mean 10 m wind speed on the cutoff day, km/h")
    solar_mj_d0: float = Field(description="Shortwave solar radiation total on the cutoff day, MJ/m²")
    pressure_mean_d0: float = Field(description="Mean surface pressure on the cutoff day, hPa")
    cloud_mean_d0: float = Field(description="Mean cloud cover on the cutoff day, %")
    tmax_roll7: float = Field(description="Mean of the max temperatures of the last 7 days (cutoff day included), °C")

    @field_validator("cutoff_date")
    @classmethod
    def _date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("cutoff_date must look like 2026-05-14")
        return v

    @model_validator(mode="after")
    def _ranges(self):
        import math
        problems = []
        for name, (lo, hi) in MANUAL_LIMITS.items():
            v = getattr(self, name)
            if v is None or not math.isfinite(v):
                problems.append(f"{name}: must be a number")
            elif not (lo <= v <= hi):
                problems.append(f"{name}={v} is outside the physically possible range {lo}..{hi}")
        if not problems:
            if self.tmin_d0 > self.tmax_d0:
                problems.append("tmin_d0 cannot be higher than tmax_d0")
            if self.tmin_d1 > self.tmax_d1:
                problems.append("tmin_d1 cannot be higher than tmax_d1")
            if self.precip_sum3 + 1e-9 < self.precip_d0:
                problems.append("precip_sum3 (3-day rain) cannot be smaller than precip_d0 (today's rain)")
            if self.tmax_roll7 > max(self.tmax_d0, self.tmax_d1, self.tmax_d2) + 15:
                problems.append("tmax_roll7 is implausibly higher than the recent daily maxima")
        if problems:
            raise ValueError("; ".join(problems))
        return self
