from fastapi.testclient import TestClient

from repurposer.main import app

client = TestClient(app)


def test_repurpose_returns_right_shape_with_mocked_claude(monkeypatch):
    """No real API key or network call -- patches call_claude directly so
    the test proves the wiring (request in, response shape out) without
    spending a token."""
    fake_thread = "1/ AI news moves fast. Here's what actually matters this week.\n2/ ..."
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_thread)

    response = client.post("/repurpose", json={"script": "A long YouTube script about AI agents.", "platform": "x"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"platform": "x", "content": fake_thread}


def test_repurpose_rejects_unsupported_platform():
    response = client.post("/repurpose", json={"script": "some script", "platform": "linkedin"})

    assert response.status_code == 400
    assert "Unsupported platform" in response.json()["detail"]


def test_repurpose_fails_loudly_when_api_key_missing(monkeypatch):
    """Simulates the real no-key situation: call_claude raises
    MissingApiKeyError exactly like it would with no ANTHROPIC_API_KEY set.
    The endpoint must surface a clear error, never a fake response."""
    from repurposer.claude_client import MissingApiKeyError

    def raise_missing_key(system_prompt, user_content):
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr("repurposer.main.call_claude", raise_missing_key)

    response = client.post("/repurpose", json={"script": "some script", "platform": "x"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY is not set" in response.json()["detail"]
