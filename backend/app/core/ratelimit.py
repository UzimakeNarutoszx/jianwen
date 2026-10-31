"""In-process sliding-window rate limiting for the auth endpoints.

The store lives in module memory, so the limits are per process: with several
uvicorn/gunicorn workers each worker keeps its own counters and the effective
limit multiplies by the worker count. Deployments with more than one worker
must move this to shared storage (Redis ``INCR``/``EXPIRE`` or a sorted set per
key) before the limits can be trusted.

Everything here is thread-safe; the auth routes are sync ``def`` handlers, so
FastAPI runs them in a thread pool.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Request

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


# phone -> timestamps of failed logins, and a separate lock stamp so the
# 15-minute lock starts at the 5th failure rather than the 1st one.
LOGIN_PHONE_FAILURE = RateLimitRule(limit=5, window_seconds=15 * 60)
LOGIN_PHONE_LOCK = RateLimitRule(limit=1, window_seconds=15 * 60)
LOGIN_IP = RateLimitRule(limit=20, window_seconds=60)

SMS_PHONE_INTERVAL = RateLimitRule(limit=1, window_seconds=60)
SMS_PHONE_DAILY = RateLimitRule(limit=10, window_seconds=24 * 60 * 60)
SMS_IP = RateLimitRule(limit=30, window_seconds=60 * 60)

SMS_CODE_PHONE_ATTEMPTS = RateLimitRule(limit=5, window_seconds=15 * 60)


class RateLimiter:
    """Sliding-window counter keyed by an arbitrary string."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def _prune(self, key: str, window_seconds: int, now: float) -> list[float]:
        cutoff = now - window_seconds
        hits = [stamp for stamp in self._hits.get(key, []) if stamp > cutoff]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def hit_count(self, key: str, window_seconds: int, now: float | None = None) -> int:
        with self._lock:
            return len(self._prune(key, window_seconds, now if now is not None else time.monotonic()))

    def is_limited(self, key: str, rule: RateLimitRule, now: float | None = None) -> bool:
        return self.hit_count(key, rule.window_seconds, now) >= rule.limit

    def record(self, key: str, rule: RateLimitRule, now: float | None = None) -> int:
        """Record one hit and return the hit count inside the window."""
        moment = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._prune(key, rule.window_seconds, moment)
            hits.append(moment)
            self._hits[key] = hits
            return len(hits)

    def reset(self, key: str | None = None) -> None:
        """Drop one key, or every key when ``key`` is None (used by tests)."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

    def seconds_until_free(self, key: str, rule: RateLimitRule, now: float | None = None) -> int:
        """Seconds until the oldest hit leaves the window (0 when not limited)."""
        moment = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._prune(key, rule.window_seconds, moment)
            if len(hits) < rule.limit:
                return 0
            oldest = hits[len(hits) - rule.limit]
            return max(1, int(round(rule.window_seconds - (moment - oldest))))


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Caller IP.

    ``X-Forwarded-For`` is client-controlled, so it is ignored unless
    ``TRUST_PROXY`` is enabled for a deployment that really sits behind a proxy.
    """
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def phone_key(phone: str) -> str:
    return (phone or "").strip()


def login_failure_key(phone: str) -> str:
    return f"login:fail:{phone_key(phone)}"


def login_lock_key(phone: str) -> str:
    return f"login:lock:{phone_key(phone)}"


def login_ip_key(ip: str) -> str:
    return f"login:ip:{ip}"


def sms_phone_key(phone: str) -> str:
    return f"sms:phone:{phone_key(phone)}"


def sms_phone_daily_key(phone: str) -> str:
    return f"sms:phone:day:{phone_key(phone)}"


def sms_ip_key(ip: str) -> str:
    return f"sms:ip:{ip}"


def sms_code_attempt_key(phone: str, purpose: str) -> str:
    return f"sms:code:{purpose}:{phone_key(phone)}"


def reset_all() -> None:
    """Clear every counter. Tests call this; nothing in the app should."""
    limiter.reset()
