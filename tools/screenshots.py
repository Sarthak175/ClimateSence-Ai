"""TEST-ONLY: screenshots every page of the built frontend (served on :4173) against the mock API (:8000)."""
import sys
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for i in range(12):   # a few synthetic prototype readings to exercise the Prototype Lab page
    requests.post("http://127.0.0.1:8000/api/sensor/reading", headers={"X-Device-Token": "dev-token"},
                  json={"device_id": "esp32-test", "dark_roof_c": 40 + i * 0.4, "reflective_roof_c": 36 + i * 0.2, "light_on": True})
pages = {"dashboard": "/", "live": "/live", "predictions": "/predictions", "modellab": "/model-lab",
         "explain": "/explainability", "climate": "/climate", "cooling": "/urban-cooling", "prototype": "/prototype"}
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for tag, vp in {"desktop": {"width": 1440, "height": 900}, "mobile": {"width": 390, "height": 844}}.items():
        pg = b.new_page(viewport=vp)
        pg.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type in ("error",) else None)
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        for name, path in pages.items():
            if tag == "mobile" and name not in ("dashboard", "predictions"): continue
            pg.goto("http://localhost:4173" + path, wait_until="networkidle"); pg.wait_for_timeout(1500)
            pg.screenshot(path=str(out / f"{tag}_{name}.png"), full_page=True)
        pg.close()
    b.close()
print("console/page errors:", errors or "none")
