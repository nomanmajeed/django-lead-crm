"""Cache-backed rate limiting for sensitive endpoints."""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(bucket: str, ip: str) -> str:
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return f"ratelimit:{bucket}:{digest}"


def is_allowed(bucket: str, ip: str, *, limit: int, window: int) -> bool:
    if not ip:
        return True
    return cache.get(_key(bucket, ip), 0) < limit


def increment(bucket: str, ip: str, *, window: int) -> None:
    if not ip:
        return
    key = _key(bucket, ip)
    cache.set(key, cache.get(key, 0) + 1, window)


def rate_limit_response() -> HttpResponse:
    return HttpResponse("Too many requests. Try again later.", status=429)


def check_path_rate_limit(request, *, bucket: str, limit_setting: str, window_setting: str) -> HttpResponse | None:
    limit = getattr(settings, limit_setting, 20)
    window = getattr(settings, window_setting, 900)
    ip = _client_ip(request)
    if not is_allowed(bucket, ip, limit=limit, window=window):
        return rate_limit_response()
    increment(bucket, ip, window=window)
    return None
