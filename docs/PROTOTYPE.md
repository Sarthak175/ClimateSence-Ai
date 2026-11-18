# Physical prototype (optional) - roof-colour experiment with ESP32

The college brief mentions a working model on a base of about 45 cm × 45 cm. **You do not need hardware for the website to work** - the *Prototype Lab* page stays empty until a real device reports. It never shows simulated values.

## Bill of materials
| Item | Qty | Notes |
|---|---|---|
| Base board 45 × 45 cm (plywood / foam board) | 1 | |
| Miniature buildings (card/foam, same size & material) | 2 | identical except the roof |
| Roof A - conventional **dark** (matte black paint/card) | 1 | |
| Roof B - **reflective** (white paint / foil-faced) or a thin **green** roof (moss/grass tray) | 1 | |
| DS18B20 waterproof temperature sensors | 2 | one under/at each roof surface, same position & contact |
| ESP32 dev board (Wi-Fi) | 1 | |
| 4.7 kΩ resistor | 1 | pull-up DATA↔3V3 |
| Low-voltage lamp (5 V LED flood or 12 V halogen on its own DC adapter) | 1 | the "sun". Mount at the same distance/angle over both roofs |
| Optional: logic-level MOSFET / relay module for lamp | 1 | on/off from GPIO 26 |

## Wiring
```
DS18B20 #1 ┐                       3V3 ──┬── 4.7kΩ ──┐
DS18B20 #2 ┴─ VDD  ─────────────── 3V3   │           │
              GND  ─────────────── GND   │           │
              DATA (both, in parallel) ──┴───────────┴── GPIO 4
Lamp (own DC supply) ── MOSFET/relay ── control from GPIO 26  (optional; share GND with ESP32)
```
Both sensors share one 1-Wire bus; each has a unique 64-bit address. Read the two addresses once (Arduino example *OneWire → DS18x20_Temperature* or *DallasTemperature → Multiple*), paste them into `DARK_ADDR` / `REFLECTIVE_ADDR` in `hardware/esp32/climatesense_esp32.ino`, and **label the physical sensors** so they cannot be swapped.

## Software setup
1. Deploy the backend and set `DEVICE_TOKEN` (random secret). On Render the blueprint generates one - copy it from the dashboard.
2. Arduino IDE → install *ESP32 board package*, libraries **OneWire, DallasTemperature, ArduinoJson**.
3. Edit Wi-Fi, `API_URL` (`https://<backend>/api/sensor/reading`), `DEVICE_TOKEN` and the two addresses; upload.
4. Open Serial Monitor (115200): you should see `POST ... -> 201`.
5. Open the website → *Prototype Lab*.

## JSON payload
```json
{"device_id":"esp32-roof-lab","dark_roof_c":41.25,"reflective_roof_c":36.80,"light_on":true}
```
Quick test without hardware (this stores a *test* reading on your own server - delete `backend/data/sensor_readings.json` afterwards and never present it as an experiment):
```bash
curl -X POST http://localhost:8000/api/sensor/reading -H "Content-Type: application/json" -H "X-Device-Token: $DEVICE_TOKEN" \
     -d '{"device_id":"curl-test","dark_roof_c":30.0,"reflective_roof_c":29.0}'
```

## Running a fair experiment
* Same lamp distance, angle, room, start temperature; wait until both sensors read the same before switching the lamp on.
* Log ≥ 30 min (heating curve), repeat 3×, swap roofs once to detect sensor bias, note room temperature.
* Report ΔT = dark − reflective over time. Say honestly that it is a small-scale demonstration of surface-reflectance (albedo), not a city-scale measurement.
* Free Render storage is ephemeral: **download the readings** (`GET /api/sensor/latest?limit=2000`) after each session.

## Safety
* Lamp: use a **low-voltage DC** lamp from a certified adapter. **Never connect mains (230 V) to the breadboard/ESP32.** Keep it ≥ 15 cm from roofs and away from foil/paper edges - hot lamps can ignite card and foam; use a heat-safe base and never leave it unattended.
* Do not use halogen lamps without a guard; they get very hot. LEDs run cooler (but give less IR heating).
* ESP32 GPIO is 3.3 V and ≤ 12 mA: switch the lamp through a MOSFET/relay module, never directly.
* Insulate all joints, keep water away from electronics (watering the green roof!), and share ground only on the low-voltage side.
* The token is a password: keep it out of screenshots and public repositories.
