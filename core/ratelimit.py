import time
import threading
import json
from pathlib import Path


_RATE_STATE_PATH = Path(__file__).parent.parent / ".rate_state"


class TokenBucket:
    def __init__(self, rate=10, burst=20):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens=1):
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def to_dict(self):
        return {
            "rate": self.rate,
            "burst": self.burst,
            "tokens": self.tokens,
            "last_refill": self.last_refill,
        }

    @classmethod
    def from_dict(cls, data):
        bucket = cls(rate=data["rate"], burst=data["burst"])
        bucket.tokens = data["tokens"]
        bucket.last_refill = data["last_refill"]
        return bucket


_buckets = {}
_buckets_lock = threading.Lock()


def _save_state():
    try:
        state = {}
        for key, bucket in _buckets.items():
            state[key] = bucket.to_dict()
        _RATE_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _load_state():
    try:
        if _RATE_STATE_PATH.exists():
            data = json.loads(_RATE_STATE_PATH.read_text(encoding="utf-8"))
            for key, bucket_data in data.items():
                _buckets[key] = TokenBucket.from_dict(bucket_data)
    except Exception:
        pass


# Load persisted rate limits on import
_load_state()


def check_rate(key, rate=10, burst=20):
    with _buckets_lock:
        if key not in _buckets:
            _buckets[key] = TokenBucket(rate, burst)
        result = _buckets[key].acquire()
        # Persist state periodically (every 10 checks)
        if hash(key) % 10 == 0:
            _save_state()
        return result
