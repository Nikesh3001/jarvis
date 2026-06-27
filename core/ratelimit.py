import time
import threading
import json
import hmac
import hashlib
from pathlib import Path


_RATE_STATE_PATH = Path(__file__).parent.parent / ".rate_state"
_HMAC_KEY = hashlib.sha256(b"FRIDAY_RATELIMIT_HMAC_2024").digest()


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


def _sign_state(state_json):
    return hmac.new(_HMAC_KEY, state_json.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_state(state_json, signature):
    expected = _sign_state(state_json)
    return hmac.compare_digest(expected, signature)


def _save_state():
    try:
        state = {}
        for key, bucket in _buckets.items():
            state[key] = bucket.to_dict()
        state_json = json.dumps(state)
        signature = _sign_state(state_json)
        _RATE_STATE_PATH.write_text(json.dumps({"data": state, "sig": signature}), encoding="utf-8")
    except Exception:
        pass


def _load_state():
    try:
        if _RATE_STATE_PATH.exists():
            raw = json.loads(_RATE_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "data" in raw and "sig" in raw:
                state_json = json.dumps(raw["data"])
                if not _verify_state(state_json, raw["sig"]):
                    return
                data = raw["data"]
            else:
                # Legacy format (no HMAC) — accept but will re-save with sig
                data = raw
            for key, bucket_data in data.items():
                _buckets[key] = TokenBucket.from_dict(bucket_data)
    except Exception:
        pass


# Load persisted rate limits on import
_load_state()

import atexit


@atexit.register
def _save_state_on_exit():
    _save_state()


def check_rate(key, rate=10, burst=20):
    with _buckets_lock:
        if key not in _buckets:
            _buckets[key] = TokenBucket(rate, burst)
        result = _buckets[key].acquire()
    return result
