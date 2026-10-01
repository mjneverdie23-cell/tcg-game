"""Polite HTTP client: per-host rate limiting, retries with exponential
backoff, and a disk cache so re-runs don't re-hit sources."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from footypred.logging_utils import get_logger

log = get_logger("data.http")

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 footypred/2.0")


class FetchError(RuntimeError):
    pass


class HttpClient:
    def __init__(self, cache_dir: str | Path, rate_limit_seconds: float = 3.0,
                 timeout_seconds: float = 30, max_retries: int = 4,
                 cache_ttl_hours: float = 12):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit = rate_limit_seconds
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self.ttl = cache_ttl_hours * 3600
        self._last_hit: dict[str, float] = {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    @classmethod
    def from_config(cls, cfg) -> "HttpClient":
        h = cfg.http
        return cls(cfg.paths.cache_dir, h.get("rate_limit_seconds", 3.0),
                   h.get("timeout_seconds", 30), h.get("max_retries", 4),
                   h.get("cache_ttl_hours", 12))

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".cache")

    def _throttle(self, host: str) -> None:
        wait = self.rate_limit - (time.monotonic() - self._last_hit.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def get_text(self, url: str, use_cache: bool = True, **params) -> str:
        return self.get_bytes(url, use_cache=use_cache, **params).decode("utf-8", "replace")

    def get_bytes(self, url: str, use_cache: bool = True, **params) -> bytes:
        if params:
            url = requests.Request("GET", url, params=params).prepare().url
        cp = self._cache_path(url)
        if use_cache and cp.exists() and time.time() - cp.stat().st_mtime < self.ttl:
            return cp.read_bytes()
        host = urlparse(url).netloc
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle(host)
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code == 200:
                    cp.write_bytes(r.content)
                    return r.content
                if r.status_code in (404, 410):
                    raise FetchError(f"{url}: HTTP {r.status_code}")
                last_exc = FetchError(f"{url}: HTTP {r.status_code}")
            except requests.RequestException as exc:
                last_exc = exc
            backoff = 2 ** (attempt + 1)
            log.debug("fetch %s failed (%s); retry in %ss", url, last_exc, backoff)
            time.sleep(backoff)
        # stale cache beats nothing
        if cp.exists():
            log.warning("using stale cache for %s", url)
            return cp.read_bytes()
        raise FetchError(f"giving up on {url}: {last_exc}")
