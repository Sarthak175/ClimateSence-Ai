from fastapi import APIRouter

from app.ml import model_quality
from app.ml.model_loader import registry

router = APIRouter(tags=["models"])


@router.get("/metrics", description="Actual MAE / MSE / R² from the Colab notebook (validation and test).")
def metrics():
    registry.require()
    return registry.metrics


@router.get("/models", description="Candidate models, tuned hyper-parameters and training metadata.")
def models():
    registry.require()
    m = registry.metrics
    return {
        "best_model": m.get("best_model"),
        "models": m.get("models"),
        "baseline": m.get("baseline_persistence"),
        "split": m.get("split"),
        "dataset": registry.metadata.get("dataset"),
        "training": registry.metadata.get("training"),
        "climate_normals": registry.metadata.get("climate_normals"),
        "environment": registry.metadata.get("environment"),
        "feature_schema": {"features": registry.schema.get("features"),
                           "details": registry.schema.get("details")},
        "warnings": registry.warnings,
    }


@router.get("/model-quality", description="Automatic readiness gate computed from the real notebook metrics.")
def model_quality_report():
    registry.require()
    return model_quality.assess(registry.metrics)
