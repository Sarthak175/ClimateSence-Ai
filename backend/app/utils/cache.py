"""Small thread-safe TTL cache with stale-if-error support."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, max_age: float) -> tuple[Any, float] | None:
        with self._lock:
            item = self._data.get(key)
        if item is None:
            return None
        stored_at, value = item
        age = time.time() - stored_at
        if age <= max_age:
            return value, age
        return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_cache = TTLCache()


def cached_call(key: str, ttl: float, fn: Callable[[], Any], stale_ok: float = 0) -> tuple[Any, dict]:
    """Return (value, meta). Falls back to a stale value (<= stale_ok seconds old)
    when `fn` raises, flagging meta['stale']=True. Re-raises if nothing usable."""
    hit = _cache.get(key, ttl)
    if hit is not None:
        return hit[0], {"cached": True, "stale": False, "age_s": round(hit[1], 1)}
    try:
        value = fn()
    except Exception:
        if stale_ok:
            old = _cache.get(key, stale_ok)
            if old is not None:
                return old[0], {"cached": True, "stale": True, "age_s": round(old[1], 1)}
        raise
    _cache.set(key, value)
    return value, {"cached": False, "stale": False, "age_s": 0.0}


def clear_cache() -> None:
    _cache.clear()
