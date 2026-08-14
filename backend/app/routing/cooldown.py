"""In-memory circuit breaker shared by the router (per provider candidate) and by
providers that internally rotate multiple keys (per key). Single-process, phase-1
appropriate — a multi-process deployment would need this in Redis/DB instead.
"""
import time

_cooldown_until: dict[str, float] = {}
_failure_streak: dict[str, int] = {}

_BASE_QUOTA_COOLDOWN = 60.0  # seconds; quota/rate-limit errors are usually per-minute
_BASE_OTHER_COOLDOWN = 15.0  # shorter — likely a blip, worth retrying sooner
_MAX_COOLDOWN = 600.0


def is_cooling_down(candidate_id: str) -> bool:
    return time.monotonic() < _cooldown_until.get(candidate_id, 0.0)


def mark_failure(candidate_id: str, *, is_quota_related: bool) -> None:
    streak = _failure_streak.get(candidate_id, 0) + 1
    _failure_streak[candidate_id] = streak
    base = _BASE_QUOTA_COOLDOWN if is_quota_related else _BASE_OTHER_COOLDOWN
    duration = min(base * (2 ** (streak - 1)), _MAX_COOLDOWN)
    _cooldown_until[candidate_id] = time.monotonic() + duration


def mark_success(candidate_id: str) -> None:
    _failure_streak[candidate_id] = 0
    _cooldown_until.pop(candidate_id, None)
