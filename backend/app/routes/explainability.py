from fastapi import APIRouter, Query

from app.services import explanation_service as es
from app.utils.validators import validate_city

router = APIRouter(tags=["explainability"])


@router.get("/explain", description="Global importance (from training) + local explanation of today's prediction.")
def explain(city: str = Query("Chennai"), basis: str = Query("today", pattern="^(today|last_complete)$")):
    city = validate_city(city)
    return {"global": es.global_explanations(), "local": es.local_explanation(city, basis)}
