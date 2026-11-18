from fastapi import APIRouter, Query

from app.ml import feature_engineering as fe
from app.services import weather_service as ws
from app.utils.validators import validate_city

router = APIRouter(tags=["weather"])


@router.get("/cities")
def cities():
    return {"cities": [{"name": n, **c} for n, c in fe.CITIES.items()]}


@router.get("/live")
def live(city: str = Query("Chennai", description="One of the supported cities")):
    """Current conditions, hourly series and 7-day daily series (Open-Meteo)."""
    return ws.live_payload(validate_city(city))


@router.get("/compare")
def compare():
    """Current conditions and 7-day maxima for all supported cities."""
    return ws.compare_cities()
