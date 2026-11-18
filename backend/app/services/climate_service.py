"""NOAA GML greenhouse-gas and NASA GISTEMP v4 retrieval.

These are MONTHLY products with a publication lag of weeks - they are fetched live
from the official servers (cached for hours) but are NOT minute-by-minute data.
"""
from __future__ import annotations

import io
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import httpx
import pandas as pd

from app.config import settings
from app.services.weather_service import HEADERS, UpstreamError
from app.utils.cache import cached_call

GASES = {
    "co2": {
        "label": "Carbon dioxide (CO₂)", "unit": "ppm",
        "page": "https://gml.noaa.gov/ccgg/trends/global.html",
        "urls": ["https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv",
                 "https://gml.noaa.gov/aftp/products/trends/co2/co2_mm_gl.csv"],
    },
    "ch4": {
        "label": "Methane (CH₄)", "unit": "ppb",
        "page": "https://gml.noaa.gov/ccgg/trends_ch4/",
        "urls": ["https://gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_mm_gl.csv",
                 "https://gml.noaa.gov/aftp/products/trends/ch4/ch4_mm_gl.csv"],
    },
    "n2o": {
        "label": "Nitrous oxide (N₂O)", "unit": "ppb",
        "page": "https://gml.noaa.gov/ccgg/trends_n2o/",
        "urls": ["https://gml.noaa.gov/webdata/ccgg/trends/n2o/n2o_mm_gl.csv",
                 "https://gml.noaa.gov/aftp/products/trends/n2o/n2o_mm_gl.csv"],
    },
}
GISTEMP_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
GISTEMP_PAGE = "https://data.giss.nasa.gov/gistemp/"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _download(urls: list[str], source: str) -> tuple[str, dict]:
    last = None
    for url in urls:
        try:
            with httpx.Client(timeout=min(settings.request_timeout_s, 15.0), follow_redirects=True, headers=HEADERS) as c:
                r = c.get(url)
            if r.status_code == 200 and r.text.strip():
                return r.text, {"data_url": url, "last_modified": r.headers.get("last-modified")}
            last = f"HTTP {r.status_code} from {url}"
        except httpx.HTTPError as exc:
            last = f"{url}: {exc}"
    raise UpstreamError(source, f"{source} download failed ({last})")


def parse_noaa_monthly(text: str) -> tuple[pd.DataFrame, str | None]:
    """Parse a NOAA GML global monthly CSV (comment lines start with '#')."""
    comment_lines = [ln for ln in text.splitlines() if ln.startswith("#")]
    created = next((ln.lstrip("# ").strip() for ln in comment_lines
                    if re.search(r"creat|updat|generat", ln, re.I)), None)
    df = pd.read_csv(io.StringIO(text), comment="#")
    df.columns = [c.strip().lower() for c in df.columns]
    need = {"year", "month", "average"}
    if not need.issubset(df.columns):
        raise ValueError(f"unexpected NOAA columns: {list(df.columns)}")
    for col in ("average", "trend", "average_unc", "trend_unc"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df.loc[df[col] <= 0, col] = pd.NA  # NOAA missing-value flags are negative (-9.99, -999.99)
    df = df.dropna(subset=["average"]).copy()
    df["year"], df["month"] = df["year"].astype(int), df["month"].astype(int)
    return df.sort_values(["year", "month"]).reset_index(drop=True), created


def parse_gistemp(text: str) -> pd.DataFrame:
    """Parse GISTEMP GLB.Ts+dSST.csv; '***' marks missing months."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("Year,")), None)
    if start is None:
        raise ValueError("GISTEMP header row not found")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), na_values=["***", "****", "*****", "NA"])
    df = df[pd.to_numeric(df["Year"], errors="coerce").notna()].copy()
    df["Year"] = df["Year"].astype(int)
    for m in MONTHS + ["J-D"]:
        df[m] = pd.to_numeric(df[m], errors="coerce")
    return df.reset_index(drop=True)


def _gas_payload(key: str) -> dict:
    spec = GASES[key]
    text, dl = _download(spec["urls"], f"NOAA GML {key.upper()}")
    df, created = parse_noaa_monthly(text)
    last = df.iloc[-1]
    series = [{
        "date": f"{int(r.year)}-{int(r.month):02d}", "year": int(r.year), "month": int(r.month),
        "average": round(float(r.average), 2),
        "trend": None if "trend" not in df.columns or pd.isna(r.trend) else round(float(r.trend), 2),
    } for r in df.itertuples(index=False)]
    year_ago = df[(df.year == last.year - 1) & (df.month == last.month)]
    yoy = None if year_ago.empty else round(float(last.average - year_ago.iloc[0].average), 2)
    return {
        "key": key, "label": spec["label"], "unit": spec["unit"],
        "latest": {"year": int(last.year), "month": int(last.month),
                   "date": f"{int(last.year)}-{int(last.month):02d}",
                   "average": round(float(last.average), 2),
                   "year_over_year_change": yoy},
        "series": series,
        "source": {"name": "NOAA Global Monitoring Laboratory (global marine-surface monthly mean)",
                   "page_url": spec["page"], "data_url": dl["data_url"],
                   "source_updated": dl["last_modified"] or created},
    }


def _gistemp_payload() -> dict:
    text, dl = _download([GISTEMP_URL], "NASA GISTEMP")
    df = parse_gistemp(text)
    monthly, annual = [], []
    for rec in df.to_dict("records"):
        year = int(rec["Year"])
        vals = [rec[m] for m in MONTHS]
        for i, v in enumerate(vals):
            if pd.notna(v):
                monthly.append({"date": f"{year}-{i + 1:02d}", "year": year, "month": i + 1,
                                "anomaly": round(float(v), 2)})
        valid = [float(v) for v in vals if pd.notna(v)]
        if pd.notna(rec["J-D"]):
            annual.append({"year": year, "anomaly": round(float(rec["J-D"]), 2),
                           "months_available": len(valid), "complete": True})
        elif valid:  # incomplete current year -> year-to-date mean, clearly flagged
            annual.append({"year": year, "anomaly": round(sum(valid) / len(valid), 2),
                           "months_available": len(valid), "complete": False})
    if not monthly:
        raise ValueError("GISTEMP contained no monthly values")
    latest = monthly[-1]
    return {
        "label": "Global surface temperature anomaly", "unit": "°C vs 1951-1980",
        "latest_month": latest, "monthly": monthly, "annual": annual,
        "source": {"name": "NASA GISS Surface Temperature Analysis (GISTEMP v4), Land-Ocean index",
                   "page_url": GISTEMP_PAGE, "data_url": dl["data_url"],
                   "source_updated": dl["last_modified"]},
        "note": "Annual values flagged complete=false are year-to-date means of the months published so far.",
    }


def climate_indicators() -> dict:
    ttl, stale = settings.climate_cache_ttl_s, settings.stale_if_error_s
    out: dict = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "update_frequency": "Monthly products with a publication lag; not minute-by-minute measurements.",
                 "indicators": {}, "errors": {}, "cache": {}}
    jobs = {k: (lambda k=k: _gas_payload(k)) for k in GASES}
    jobs["gistemp"] = _gistemp_payload
    def run(item):
        key, fn = item
        try:
            return key, cached_call(f"climate:{key}", ttl, fn, stale_ok=stale), None
        except Exception as exc:  # one failing source must not blank the others
            return key, None, str(exc)

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:      # all four downloads in parallel
        for key, res, err in pool.map(run, jobs.items()):
            if err:
                out["errors"][key] = err
            else:
                out["indicators"][key], out["cache"][key] = res
    if not out["indicators"]:
        raise UpstreamError("NOAA/NASA", "; ".join(out["errors"].values()) or "all climate sources failed")
    return out
