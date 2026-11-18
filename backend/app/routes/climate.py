from fastapi import APIRouter

from app.services import climate_service

router = APIRouter(tags=["climate"])


@router.get("/climate-indicators",
            description="NOAA GML CO₂/CH₄/N₂O monthly global means and NASA GISTEMP v4 anomalies.")
def climate_indicators():
    return climate_service.climate_indicators()
