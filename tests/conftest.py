import pytest

from repurposer import rate_limit


@pytest.fixture(autouse=True)
def _clean_rate_limit_state_between_tests():
    """Every test shares one FastAPI `app` (and therefore one in-memory rate
    limiter) via TestClient, which always reports the same fake client IP.
    Without this, a test in test_repurpose.py that posts several times could
    tip a later test in test_rate_limit.py over its budget, or vice versa,
    purely because of module import/run order -- this keeps every test
    starting from a clean slate regardless of order."""
    rate_limit.reset_rate_limits()
    yield
    rate_limit.reset_rate_limits()
