import numpy as np
import pandas as pd

from app.ml import feature_engineering as fe
from tests.synthetic import synthetic_hourly


def _daily(seed=0):
    return fe.hourly_to_daily(synthetic_hourly(13.0, "2024-01-01", "2024-03-31", seed))


def test_target_not_in_features():
    assert fe.TARGET not in fe.FEATURES
    assert len(set(fe.FEATURES)) == len(fe.FEATURES)


def test_no_leakage_future_changes_do_not_alter_features():
    d = _daily()
    base = fe.make_feature_frame(d, 13.0, 80.0)
    cutoff = pd.Timestamp("2024-02-20")
    d2 = d.copy()
    future = d2["date"] > cutoff
    d2.loc[future, ["tmax", "tmin", "rh_mean", "precip_sum", "wind_mean", "pressure_mean",
                    "cloud_mean", "solar_mj"]] += 50  # corrupt EVERYTHING after the cutoff
    changed = fe.make_feature_frame(d2, 13.0, 80.0)
    a = base[base["date"] <= cutoff][fe.FEATURES].to_numpy()
    b = changed[changed["date"] <= cutoff][fe.FEATURES].to_numpy()
    assert np.allclose(a, b, equal_nan=True)


def test_target_is_next_day_max():
    d = _daily()
    f = fe.make_feature_frame(d, 13.0, 80.0).set_index("date")
    day = pd.Timestamp("2024-02-10")
    nxt = d.set_index("date").loc[day + pd.Timedelta(days=1), "tmax"]
    assert f.loc[day, fe.TARGET] == nxt


def test_rolling_windows_use_only_past():
    d = _daily().set_index("date")
    f = fe.make_feature_frame(d.reset_index(), 13.0, 80.0).set_index("date")
    day = pd.Timestamp("2024-02-10")
    expect = d["tmax"].loc[day - pd.Timedelta(days=6): day].mean()
    assert abs(f.loc[day, "tmax_roll7"] - expect) < 1e-9


def test_doy_calendar_handles_leap_day():
    got = fe.day_of_year_365(pd.to_datetime(["2024-02-28", "2024-02-29", "2024-03-01", "2024-12-31", "2023-03-01"]))
    assert list(got) == [59, 59, 60, 365, 60]


def test_missing_days_produce_nan_not_fabrication():
    d = _daily()
    d = d[d["date"] != pd.Timestamp("2024-02-09")]
    f = fe.make_feature_frame(d, 13.0, 80.0).set_index("date")
    assert np.isnan(f.loc[pd.Timestamp("2024-02-10"), "tmax_d1"])


def test_units_validation():
    assert fe.validate_units({**{k: v for k, v in fe.EXPECTED_UNITS.items()}}) == []
    assert fe.validate_units({"temperature_2m": "°F"})


def test_heat_classification():
    assert fe.classify_heat(30, 29, 33, 34)["label"] == "Normal"
    assert fe.classify_heat(31, 29, 33, 34)["label"] == "Elevated"
    assert fe.classify_heat(33.5, 29, 33, 34)["label"] == "High"
    assert fe.classify_heat(35, 29, 33, 34)["label"] == "Severe"
