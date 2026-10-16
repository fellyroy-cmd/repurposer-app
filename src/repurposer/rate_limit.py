"""
Dependency-free in-process rate limiter for the expensive endpoints
(/repurpose and /repurpose-all) -- the ones that spend real Claude tokens.

This is a fixed-window limiter: each client gets a budget of N requests per
window-of-T-seconds, keyed by client IP. It lives in memory, so it resets if
the process restarts and doesn't share state across multiple server
instances -- fine for this project's single-process deploy target, and a lot
simpler than pulling in a library for one counter per client.
"""

import os
import time
from collections import defaultdict
from typing import Dict, List

# Configurable via env, same pattern as config.MODEL -- never hardcoded
# elsewhere in the app. Defaults: 10 requests per 60-second window per client.
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "10"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

# client_id -> list of request timestamps (seconds) still inside the window.
_request_log: Dict[str, List[float]] = defaultdict(list)


class RateLimitExceeded(Exception):
    """Raised when a client has hit the request budget for the current window."""


def check_rate_limit(client_id: str) -> None:
    """Records this request and raises RateLimitExceeded if the client has
    made more than RATE_LIMIT_MAX_REQUESTS requests in the trailing
    RATE_LIMIT_WINDOW_SECONDS. Sliding by eviction: old timestamps outside
    the window are dropped on every call, so the window always slides
    forward instead of resetting on a fixed clock boundary."""
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    timestamps = _request_log[client_id]
    # Drop anything older than the window before counting.
    fresh = [t for t in timestamps if t > window_start]

    if len(fresh) >= RATE_LIMIT_MAX_REQUESTS:
        _request_log[client_id] = fresh
        raise RateLimitExceeded(
            f"Rate limit hit: max {RATE_LIMIT_MAX_REQUESTS} requests per "
            f"{RATE_LIMIT_WINDOW_SECONDS} seconds for this endpoint. Wait a "
            f"moment and try again."
        )

    fresh.append(now)
    _request_log[client_id] = fresh


def reset_rate_limits() -> None:
    """Clears all tracked request history. Used by tests so one test's
    requests don't bleed into the next test's limit count -- every test
    using TestClient shares the same client IP ("testclient"), so without a
    reset, test order would silently affect results."""
    _request_log.clear()
