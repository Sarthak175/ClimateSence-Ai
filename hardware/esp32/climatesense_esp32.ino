/*
  ClimateSense AI - ESP32 roof-temperature node
  Two DS18B20 sensors (dark roof, reflective/green roof) -> Wi-Fi -> POST /api/sensor/reading

  Libraries (Arduino IDE > Library Manager): OneWire, DallasTemperature, ArduinoJson
  Board: "ESP32 Dev Module"

  Wiring (see docs/PROTOTYPE.md):
    DS18B20 VDD  -> 3V3        DS18B20 GND -> GND
    DS18B20 DATA (both sensors in parallel on ONE bus) -> GPIO 4, plus a 4.7 kΩ resistor DATA<->3V3
    Optional lamp relay/MOSFET control pin -> GPIO 26 (lamp on its OWN low-voltage supply, never mains)
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// ======== EDIT THESE ========
const char* WIFI_SSID   = "YOUR_WIFI";
const char* WIFI_PASS   = "YOUR_PASSWORD";
const char* API_URL     = "https://YOUR-BACKEND.onrender.com/api/sensor/reading";  // HTTPS URL of your backend
const char* DEVICE_TOKEN = "SAME_AS_DEVICE_TOKEN_ON_SERVER";
const char* DEVICE_ID   = "esp32-roof-lab";
const unsigned long SEND_EVERY_MS = 10000;     // one reading every 10 s
// Dallas sensors have unique 64-bit addresses. Run the "Multiple" example once, read the two
// addresses from the serial monitor and paste them here, so that "dark" and "reflective" never swap.
DeviceAddress DARK_ADDR       = {0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01};
DeviceAddress REFLECTIVE_ADDR = {0x28, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02};
// ============================

const int ONE_WIRE_PIN = 4;
const int LAMP_PIN = 26;          // optional; set to -1 if unused
const bool LAMP_ON_AT_START = true;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature sensors(&oneWire);
unsigned long lastSend = 0;

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to Wi-Fi");
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) { delay(500); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? "\nWi-Fi connected" : "\nWi-Fi FAILED (will retry)");
}

bool validReading(float c) {
  // DEVICE_DISCONNECTED_C = -127, power-on default = 85.0 -> both mean "not a real measurement"
  return c > -55.0 && c < 125.0 && c != 85.0 && c != DEVICE_DISCONNECTED_C;
}

void setup() {
  Serial.begin(115200);
  if (LAMP_PIN >= 0) { pinMode(LAMP_PIN, OUTPUT); digitalWrite(LAMP_PIN, LAMP_ON_AT_START ? HIGH : LOW); }
  sensors.begin();
  connectWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) { connectWifi(); delay(2000); return; }
  if (millis() - lastSend < SEND_EVERY_MS) return;
  lastSend = millis();

  sensors.requestTemperatures();
  float dark = sensors.getTempC(DARK_ADDR);
  float refl = sensors.getTempC(REFLECTIVE_ADDR);
  if (!validReading(dark) || !validReading(refl)) {
    Serial.println("Sensor read error - nothing sent (never send made-up numbers)");
    return;
  }

  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["dark_roof_c"] = dark;
  doc["reflective_roof_c"] = refl;
  if (LAMP_PIN >= 0) doc["light_on"] = digitalRead(LAMP_PIN) == HIGH;
  String body; serializeJson(doc, body);

  WiFiClientSecure client;
  client.setInsecure();   // quick start. For production pin the server certificate instead (client.setCACert(...)).
  HTTPClient http;
  http.setTimeout(15000);
  if (http.begin(client, API_URL)) {
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Token", DEVICE_TOKEN);
    int code = http.POST(body);
    Serial.printf("POST %s -> %d | dark %.2f C, reflective %.2f C\n", API_URL, code, dark, refl);
    http.end();
  }
}
