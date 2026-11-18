"""Diagnose the live-data chain. Run on YOUR machine with the backend running:

    python tools/check_live_apis.py            # backend at http://localhost:8000
    python tools/check_live_apis.py http://localhost:8000

Step A calls the real upstream servers directly (tells you whether your network can reach them).
Step B calls your local ClimateSense API (tells you whether the backend serves them correctly).
"""
import sys
import httpx

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
UA = {"User-Agent": "ClimateSenseAI-check/1.0"}
results = []


def check(name, fn):
    try:
        msg = fn()
        results.append((name, True, msg))
        print(f"  PASS  {name}: {msg}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, False, str(exc)[:200]))
        print(f"  FAIL  {name}: {str(exc)[:200]}")


def get(url, **params):
    r = httpx.get(url, params=params or None, timeout=30, follow_redirects=True, headers=UA)
    r.raise_for_status()
    return r


print("\nA. Real upstream servers (direct from this computer)")
def om():
    j = get("https://api.open-meteo.com/v1/forecast", latitude=13.08, longitude=80.27,
            current="temperature_2m,relative_humidity_2m", timezone="Asia/Kolkata").json()
    return f"Chennai now {j['current']['temperature_2m']} {j['current_units']['temperature_2m']} at {j['current']['time']}"
check("Open-Meteo forecast", om)
check("Open-Meteo historical forecast", lambda: "rows=%d" % len(get(
    "https://historical-forecast-api.open-meteo.com/v1/forecast", latitude=13.08, longitude=80.27,
    start_date="2024-01-01", end_date="2024-01-02", hourly="temperature_2m").json()["hourly"]["time"]))
check("Open-Meteo ERA5-Land archive", lambda: "days=%d" % len(get(
    "https://archive-api.open-meteo.com/v1/archive", latitude=13.08, longitude=80.27,
    start_date="2020-01-01", end_date="2020-01-03", daily="temperature_2m_max",
    models="era5_land", timezone="Asia/Kolkata").json()["daily"]["time"]))
check("NOAA GML CO2", lambda: f"{len(get('https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv').text)} bytes")
check("NASA GISTEMP", lambda: f"{len(get('https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv').text)} bytes")

print(f"\nB. Your local API ({API})")
check("GET /api/health", lambda: str(get(f"{API}/api/health").json())[:150])
def live():
    j = get(f"{API}/api/live", city="Chennai").json()
    c = j.get("current", {})
    return f"current={c.get('temperature_c')} C, hourly points={len(j.get('hourly', []))}, keys={list(j)[:6]}"
check("GET /api/live?city=Chennai", live)
check("GET /api/climate-indicators", lambda: "keys=" + ",".join(get(f"{API}/api/climate-indicators").json().keys()))
def predict():
    r = httpx.get(f"{API}/api/predict", params={"city": "Chennai"}, timeout=60, headers=UA)
    if r.status_code == 503:
        return "503 model_unavailable (expected until training finished - not a failure of live data)"
    r.raise_for_status()
    return f"predicted={r.json().get('prediction', {})}"[:150]
check("GET /api/predict?city=Chennai", predict)

failed = [n for n, ok, _ in results if not ok]
print("\nSUMMARY:", "ALL OK" if not failed else "FAILED -> " + ", ".join(failed))
if failed:
    print("If A fails: network/firewall/VPN blocks that server. If only B fails: send the FAIL lines to the developer.")
