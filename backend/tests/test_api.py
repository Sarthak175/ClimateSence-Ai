import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.ml import feature_engineering as fe
from app.ml.model_loader import registry
from app.services import climate_service, weather_service
from app.utils.cache import clear_cache
from tests.synthetic import forecast_response, make_test_artifacts


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    d = tmp_path_factory.mktemp("models")
    make_test_artifacts(d)
    return d


@pytest.fixture()
def client(artifacts, monkeypatch, tmp_path):
    from app import main
    clear_cache()
    registry.model_dir = artifacts
    registry.load()
    assert registry.loaded, registry.reason

    def fake_get(url, params):
        today = pd.Timestamp.utcnow().tz_convert(None).normalize() + pd.Timedelta(hours=5.5)
        today = today.normalize()
        lat = params["latitude"]
        if isinstance(lat, str):  # multi-location
            lats = [float(x) for x in lat.split(",")]
            lons = [float(x) for x in params["longitude"].split(",")]
            return [forecast_response(a, b, today, 3, 7) for a, b in zip(lats, lons)]
        return forecast_response(lat, params["longitude"], today)
    monkeypatch.setattr(weather_service, "http_get_json", fake_get)
    object.__setattr__(settings, "device_token", "secret-token")
    from app.services import sensor_service
    monkeypatch.setattr(sensor_service.store, "path", tmp_path / "s.json")
    sensor_service.store._items = []
    with TestClient(main.app) as c:
        registry.model_dir = artifacts
        registry.load()
        yield c


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["model"]["loaded"] is True


def test_live(client):
    r = client.get("/api/live?city=chennai")
    assert r.status_code == 200
    j = r.json()
    assert j["city"] == "Chennai" and j["current"]["temperature_c"] is not None
    assert j["today"] is not None and len(j["hourly"]) > 24 and "model-derived" in j["note"]
    assert j["timestamps"]["fetched_at_utc"]


def test_unknown_city(client):
    r = client.get("/api/live?city=Atlantis")
    assert r.status_code == 404 and r.json()["detail"]["error"] == "unknown_city"


def test_predict(client):
    r = client.get("/api/predict?city=Delhi")
    assert r.status_code == 200, r.text
    j = r.json()
    p = j["prediction"]["predicted_tmax_c"]
    assert 10 < p < 55
    assert set(j["features_used"]) == set(fe.FEATURES)
    assert j["heat_risk"]["label"] in {"Normal", "Elevated", "High", "Severe"}
    assert j["prediction"]["interval"]["lower_c"] < p < j["prediction"]["interval"]["upper_c"]
    j2 = client.get("/api/predict?city=Delhi&basis=last_complete").json()
    assert j2["prediction"]["cutoff_date"] < j["prediction"]["cutoff_date"]


def test_predict_matches_manual_model_call(client):
    j = client.get("/api/predict?city=Mumbai").json()
    x = pd.DataFrame([j["features_used"]])[fe.FEATURES]
    assert abs(registry.model.predict(x)[0] - j["prediction"]["predicted_tmax_c"]) < 0.06


def test_predict_all_and_compare(client):
    j = client.get("/api/predict/all").json()
    assert len(j["cities"]) == 6 and not j["errors"]
    c = client.get("/api/compare").json()
    assert len(c["cities"]) == 6


def test_explain_sums_to_prediction(client):
    r = client.get("/api/explain?city=Kolkata")
    assert r.status_code == 200, r.text
    loc = r.json()["local"]
    total = loc["base_value_c"] + sum(i["contribution_c"] for i in loc["all"])
    assert abs(total - loc["predicted_tmax_c"]) < 0.05


def test_metrics_and_models(client):
    assert client.get("/api/metrics").status_code == 200
    assert client.get("/api/models").status_code == 200


def test_sensor_auth_and_flow(client):
    assert client.get("/api/sensor/latest").json()["available"] is False
    body = {"device_id": "esp32-1", "dark_roof_c": 41.2, "reflective_roof_c": 36.8}
    assert client.post("/api/sensor/reading", json=body).status_code == 401
    assert client.post("/api/sensor/reading", json=body, headers={"X-Device-Token": "bad"}).status_code == 401
    ok = client.post("/api/sensor/reading", json=body, headers={"X-Device-Token": "secret-token"})
    assert ok.status_code == 201 and ok.json()["stored"]["difference_c"] == 4.4
    bad = client.post("/api/sensor/reading", json={**body, "dark_roof_c": 85.0},
                      headers={"X-Device-Token": "secret-token"})
    assert bad.status_code == 422
    assert client.get("/api/sensor/latest").json()["latest"]["dark_roof_c"] == 41.2


def test_upstream_failure_is_502_not_fake_data(client, monkeypatch):
    clear_cache()

    def boom(url, params):
        raise weather_service.UpstreamError("Open-Meteo", "down")
    monkeypatch.setattr(weather_service, "http_get_json", boom)
    r = client.get("/api/predict?city=Chennai")
    assert r.status_code == 502 and r.json()["detail"]["error"] == "upstream_unavailable"


def test_model_missing_gives_503(client, tmp_path):
    registry.model_dir = tmp_path  # empty directory
    registry.load()
    r = client.get("/api/predict?city=Chennai")
    assert r.status_code == 503 and r.json()["detail"]["error"] == "model_unavailable"
    assert client.get("/api/metrics").status_code == 503
    assert client.get("/api/health").json()["model"]["loaded"] is False


NOAA_SAMPLE = """# COMMENT line
# File Creation: Mon Oct  6 2025
year,month,decimal,average,average_unc,trend,trend_unc
2024,12,2024.958,422.90,0.10,424.10,0.10
2025,1,2025.042,424.00,0.10,424.50,0.10
2025,2,2025.125,-9.99,-9.99,-9.99,-9.99
"""
GISS_SAMPLE = """Land-Ocean: Global Means
Year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec,J-D,D-N,DJF,MAM,JJA,SON
2023,0.87,0.98,1.20,1.00,0.94,1.08,1.18,1.20,1.48,1.34,1.44,1.35,1.17,1.15,0.95,1.04,1.15,1.42
2025,1.36,1.26,1.35,1.22,***,***,***,***,***,***,***,***,***,***,***,***,***,***
"""


def test_noaa_and_gistemp_parsing():
    df, created = climate_service.parse_noaa_monthly(NOAA_SAMPLE)
    assert len(df) == 2 and df.iloc[-1].month == 1 and "Creation" in created
    g = climate_service.parse_gistemp(GISS_SAMPLE)
    assert g.loc[g.Year == 2025, "May"].isna().all() and g.loc[g.Year == 2023, "J-D"].iloc[0] == 1.17


def test_climate_endpoint_with_mocked_sources(client, monkeypatch):
    clear_cache()

    def fake_dl(urls, source):
        return (GISS_SAMPLE if "GISTEMP" in source else NOAA_SAMPLE), {"data_url": urls[0], "last_modified": "x"}
    monkeypatch.setattr(climate_service, "_download", fake_dl)
    j = client.get("/api/climate-indicators").json()
    assert set(j["indicators"]) == {"co2", "ch4", "n2o", "gistemp"}
    g = j["indicators"]["gistemp"]
    assert g["latest_month"]["date"] == "2025-04"
    assert [a for a in g["annual"] if a["year"] == 2025][0]["complete"] is False
    assert j["indicators"]["co2"]["latest"]["date"] == "2025-01"


def test_model_quality_gate_reads_real_metrics(client):
    r = client.get("/api/model-quality")
    assert r.status_code == 200
    j = r.json()
    assert j["verdict"] in {"ready", "limited", "not_ready"}
    assert {c["name"] for c in j["checks"]} >= {"Beats the persistence baseline", "Prediction interval is honest"}


def test_live_payload_exposes_exact_source_url(client):
    j = client.get("/api/live", params={"city": "Chennai"}).json()
    assert j["source"]["request_url"].startswith("https://api.open-meteo.com/v1/forecast?")
    assert "latitude=13.08" in j["source"]["request_url"]


MANUAL_OK = dict(city="Chennai", cutoff_date="2026-05-14", tmax_d0=38.0, tmin_d0=28.0, tmax_d1=37.5, tmax_d2=37.0,
                 tmin_d1=27.5, rh_mean_d0=60.0, precip_d0=0.0, precip_sum3=0.0, wind_mean_d0=12.0,
                 solar_mj_d0=24.0, pressure_mean_d0=1005.0, cloud_mean_d0=30.0, tmax_roll7=37.0)


def test_manual_prediction_matches_direct_model_call(client):
    r = client.post("/api/predict/manual", json=MANUAL_OK)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "manual" and j["prediction"]["prediction_date"] == "2026-05-15"
    from app.services.prediction_service import build_manual_features
    x = build_manual_features("Chennai", "2026-05-14", {k: v for k, v in MANUAL_OK.items() if k not in ("city", "cutoff_date")})
    assert list(x.columns) == fe.FEATURES
    assert j["prediction"]["predicted_tmax_c"] == round(float(registry.model.predict(x)[0]), 1)
    assert abs(j["features_used"]["tmax_roll3"] - (38.0 + 37.5 + 37.0) / 3) < 1e-3
    e = j["explanation"]
    assert abs(sum(i["contribution_c"] for i in e["all"]) - (e["predicted_tmax_c"] - e["base_value_c"])) < 0.05


def test_manual_responds_to_inputs(client):
    hot = client.post("/api/predict/manual", json=MANUAL_OK).json()["prediction"]["predicted_tmax_c"]
    cool = client.post("/api/predict/manual", json={**MANUAL_OK, "tmax_d0": 30.0, "tmax_d1": 30.0, "tmax_d2": 30.0,
                                                    "tmax_roll7": 30.0, "tmin_d0": 24.0, "tmin_d1": 24.0}).json()["prediction"]["predicted_tmax_c"]
    assert hot > cool


@pytest.mark.parametrize("patch,needle", [
    ({"rh_mean_d0": 140}, "rh_mean_d0"),
    ({"tmin_d0": 45.0, "tmax_d0": 30.0}, "tmin_d0"),
    ({"precip_d0": 10.0, "precip_sum3": 2.0}, "precip_sum3"),
    ({"cutoff_date": "14-05-2026"}, "cutoff_date"),
    ({"tmax_roll7": None}, "tmax_roll7"),
])
def test_manual_rejects_bad_input_without_guessing(client, patch, needle):
    body = {**MANUAL_OK, **patch}
    if body.get("tmax_roll7") is None:
        body.pop("tmax_roll7")
    r = client.post("/api/predict/manual", json=body)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["error"] == "invalid_input" and needle in d["message"]


def test_manual_schema_endpoint(client):
    j = client.get("/api/predict/manual/schema").json()
    assert len(j["fields"]) == 13 and "Chennai" in j["cities"]


def test_manual_503_without_model(client, tmp_path):
    registry.model_dir = tmp_path
    registry.load()
    r = client.post("/api/predict/manual", json=MANUAL_OK)
    assert r.status_code == 503
