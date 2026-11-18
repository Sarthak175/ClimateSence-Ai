import hmac

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import settings
from app.services.sensor_service import store
from app.utils.validators import SensorReading

router = APIRouter(tags=["sensors"])


@router.get("/sensor/latest", description="Latest real ESP32 readings (empty if no hardware has reported).")
def latest(limit: int = Query(200, ge=1, le=2000)):
    return store.latest(limit)


@router.post("/sensor/reading", status_code=201,
             description="Submit a reading from the ESP32. Requires header `X-Device-Token`.")
def add_reading(reading: SensorReading, x_device_token: str | None = Header(default=None)):
    if not settings.device_token:
        raise HTTPException(503, detail={"error": "sensor_writes_disabled",
                                         "message": "DEVICE_TOKEN is not configured on the server."})
    if not x_device_token or not hmac.compare_digest(x_device_token, settings.device_token):
        raise HTTPException(401, detail={"error": "invalid_device_token",
                                         "message": "Missing or invalid X-Device-Token header."})
    return {"stored": store.add(reading)}
