import pytest
from fastapi.testclient import TestClient

from repurposer import rate_limit
from repurposer.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(monkeypatch):
    """Every test in this module gets a clean limiter and a small, known
    budget -- TestClient always uses the same fake client IP ("testclient"),
    so without a reset+override, one test's requests would bleed into the
    next test's count and tests would fail depending on run order."""
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(rate_limit, "RATE_LIMIT_WINDOW_SECONDS", 60)
    rate_limit.reset_rate_limits()
    yield
    rate_limit.reset_rate_limits()


def _mock_claude(monkeypatch, fake_text="some platform text"):
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_text)


def test_requests_under_the_limit_succeed(monkeypatch):
    """With a budget of 3, the first 3 calls to /repurpose should all go
    through normally -- rate limiting shouldn't touch traffic that's
    actually within budget."""
    _mock_claude(monkeypatch)

    for _ in range(3):
        response = client.post("/repurpose", json={"script": "some script", "platform": "x"})
        assert response.status_code == 200


def test_request_over_the_limit_returns_429(monkeypatch):
    """The 4th call within the window, on top of a budget of 3, must be
    rejected with a clear 429 naming the limit -- not silently dropped or
    queued."""
    _mock_claude(monkeypatch)

    for _ in range(3):
        client.post("/repurpose", json={"script": "some script", "platform": "x"})

    response = client.post("/repurpose", json={"script": "some script", "platform": "x"})

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


def test_repurpose_all_shares_the_same_rate_limit_budget(monkeypatch):
    """/repurpose and /repurpose-all are both token-spending endpoints, so
    they share one budget per client, not independent limits -- otherwise
    someone could dodge the limit by alternating endpoints."""
    _mock_claude(monkeypatch)

    for _ in range(3):
        response = client.post("/repurpose", json={"script": "some script", "platform": "x"})
        assert response.status_code == 200

    response = client.post("/repurpose-all", json={"script": "some script", "platforms": ["x"]})

    assert response.status_code == 429
    assert "Rate limit" in response.json()["detail"]


def test_health_is_never_rate_limited(monkeypatch):
    """/health costs no Claude tokens, so it must never be subject to the
    limit -- a monitoring/uptime check hitting it dozens of times a minute
    should never get a 429."""
    _mock_claude(monkeypatch)

    # Burn through the budget on /repurpose first.
    for _ in range(3):
        client.post("/repurpose", json={"script": "some script", "platform": "x"})
    # Confirm the budget really is exhausted for the limited endpoint.
    limited_response = client.post("/repurpose", json={"script": "some script", "platform": "x"})
    assert limited_response.status_code == 429

    # /health should still work, every time, regardless of the exhausted budget.
    for _ in range(5):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
