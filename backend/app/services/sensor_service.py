"""Storage for ESP32 prototype readings (real hardware only - never simulated)."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.utils.validators import SensorReading


class SensorStore:
    def __init__(self, path: Path, max_items: int) -> None:
        self.path, self.max_items = Path(path), max_items
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                self._items = json.loads(self.path.read_text())[-self.max_items:]
        except Exception:
            self._items = []

    def _persist(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._items))
            tmp.replace(self.path)
        except OSError:
            pass  # read-only / ephemeral disk: keep working in memory

    def add(self, reading: SensorReading) -> dict:
        ts = reading.timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        item = {
            "device_id": reading.device_id,
            "timestamp": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dark_roof_c": round(reading.dark_roof_c, 2),
            "reflective_roof_c": round(reading.reflective_roof_c, 2),
            "difference_c": round(reading.dark_roof_c - reading.reflective_roof_c, 2),
            "ambient_c": None if reading.ambient_c is None else round(reading.ambient_c, 2),
            "light_on": reading.light_on,
        }
        with self._lock:
            self._items.append(item)
            self._items = self._items[-self.max_items:]
            self._persist()
        return item

    def latest(self, limit: int = 200) -> dict:
        with self._lock:
            items = list(self._items)
        if not items:
            return {"available": False, "latest": None, "readings": [], "count": 0}
        return {"available": True, "latest": items[-1], "readings": items[-limit:], "count": len(items)}


store = SensorStore(settings.sensor_store_path, settings.sensor_max_readings)
