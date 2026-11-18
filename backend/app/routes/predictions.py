from fastapi import APIRouter, Query

from app.services import prediction_service as ps
from app.utils.validators import ManualInput, validate_city

router = APIRouter(tags=["predictions"])
BASIS_DOC = ("today: cutoff = today (forecast for tomorrow, remaining hours of today come from the "
             "weather model); last_complete: cutoff = yesterday (all 24 h observed/analysed).")


@router.get("/predict", description="Next-day maximum temperature from the exported ML model. " + BASIS_DOC)
def predict(city: str = Query("Chennai"), basis: str = Query("today", pattern="^(today|last_complete)$")):
    return ps.predict_city(validate_city(city), basis)


@router.get("/predict/all", description="Predictions for every supported city.")
def predict_all(basis: str = Query("today", pattern="^(today|last_complete)$")):
    return ps.predict_all(basis)


@router.post("/predict/manual", description="What-if prediction from values typed by the user (same trained model, "
             "same feature code). Every field is required; nothing is estimated or filled in.")
def predict_manual(body: ManualInput):
    city = validate_city(body.city)
    values = body.model_dump(exclude={"city", "cutoff_date"})
    return ps.predict_manual(city, body.cutoff_date, values)


@router.get("/predict/manual/schema", description="Fields, units, hard limits and typical training ranges for the manual form.")
def manual_schema():
    from app.ml import feature_engineering as fe
    from app.ml.model_loader import registry
    from app.utils.validators import MANUAL_LIMITS
    registry.require()
    stats = registry.schema.get("feature_stats", {})
    fields = []
    for f in ps.MANUAL_FIELDS:
        label, unit = fe.FEATURE_INFO[f]
        lo, hi = MANUAL_LIMITS[f]
        st = stats.get(f, {})
        fields.append({"name": f, "label": label, "unit": unit, "min": lo, "max": hi,
                       "train_min": st.get("min"), "train_max": st.get("max"), "train_median": st.get("median")})
    return {"cities": list(fe.CITIES), "fields": fields}
