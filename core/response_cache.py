import time
import hashlib
import json
import threading
from collections import OrderedDict


class ResponseCache:
    def __init__(self, max_size=100, default_ttl=300):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def _make_key(self, messages, model="", temperature=0.1):
        content = json.dumps([
            {"role": m["role"], "content": m.get("content", "")[:500]}
            for m in messages[-10:]
        ], sort_keys=True)
        raw = f"{model}|{temperature}|{content}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, messages, model="", temperature=0.1):
        key = self._make_key(messages, model, temperature)
        with self._lock:
            if key not in self._cache:
                return None
            entry = self._cache[key]
            if time.time() - entry["time"] > entry.get("ttl", self._default_ttl):
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry["result"]

    def set(self, messages, result, model="", temperature=0.1, ttl=None):
        key = self._make_key(messages, model, temperature)
        with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = {
                "result": result,
                "time": time.time(),
                "ttl": ttl or self._default_ttl,
            }

    def invalidate(self, messages=None, model=""):
        with self._lock:
            if messages is None:
                self._cache.clear()
                return
            key = self._make_key(messages, model)
            self._cache.pop(key, None)

    def stats(self):
        with self._lock:
            now = time.time()
            active = sum(1 for e in self._cache.values() if now - e["time"] < e.get("ttl", self._default_ttl))
            return {
                "size": len(self._cache),
                "active": active,
                "expired": len(self._cache) - active,
                "max_size": self._max_size,
                "default_ttl": self._default_ttl,
            }

    def hit_rate_tracker(self):
        return _HitRateTracker(self)


class _HitRateTracker:
    def __init__(self, cache):
        self._cache = cache
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    def record_hit(self):
        with self._lock:
            self._hits += 1

    def record_miss(self):
        with self._lock:
            self._misses += 1

    def rate(self):
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def report(self):
        return {"hits": self._hits, "misses": self._misses, "rate": round(self.rate(), 3)}
