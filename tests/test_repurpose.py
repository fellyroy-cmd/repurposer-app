import json

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
    assert body == {"platform": "x", "content": fake_thread, "carousel": None}


def test_repurpose_rejects_unsupported_platform():
    response = client.post("/repurpose", json={"script": "some script", "platform": "tiktok"})

    assert response.status_code == 400
    assert "Unsupported platform" in response.json()["detail"]


def test_repurpose_returns_plain_text_for_linkedin(monkeypatch):
    """LinkedIn is a plain-text platform like X -- same shape, different
    prompt. Proves the new platform is wired through main.py correctly."""
    fake_post = "Hook line that earns the click.\n\nThe rest of the post..."
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_post)

    response = client.post("/repurpose", json={"script": "A script about AI agents.", "platform": "linkedin"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"platform": "linkedin", "content": fake_post, "carousel": None}


def test_repurpose_parses_instagram_json_into_carousel(monkeypatch):
    """Instagram is a structured platform: Claude's raw text must be valid
    JSON, and the endpoint parses it into the typed InstagramCarousel shape
    instead of returning a wall of text."""
    fake_json = json.dumps(
        {
            "caption": "AI agents, explained in 6 slides. #AI #Automation",
            "slides": [
                "Slide 1: the hook",
                "Slide 2: the problem",
                "Slide 3: the idea",
                "Slide 4: how it works",
                "Slide 5: the takeaway",
                "Slide 6: join the Discord",
            ],
        }
    )
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_json)

    response = client.post("/repurpose", json={"script": "A script about AI agents.", "platform": "instagram"})

    assert response.status_code == 200
    body = response.json()
    assert body["platform"] == "instagram"
    assert body["content"] is None
    assert body["carousel"]["caption"] == "AI agents, explained in 6 slides. #AI #Automation"
    assert len(body["carousel"]["slides"]) == 6


def test_repurpose_fails_loudly_on_malformed_instagram_json(monkeypatch):
    """If Claude ignores the 'respond with only JSON' instruction, the
    endpoint must surface a clear 502, never guess or silently drop slides."""
    monkeypatch.setattr(
        "repurposer.main.call_claude",
        lambda system_prompt, user_content: "Sure! Here's your carousel: slide 1 is...",
    )

    response = client.post("/repurpose", json={"script": "A script about AI agents.", "platform": "instagram"})

    assert response.status_code == 502
    assert "instagram" in response.json()["detail"]


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
