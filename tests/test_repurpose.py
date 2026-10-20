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
    response = client.post("/repurpose", json={"script": "some script", "platform": "facebook"})

    assert response.status_code == 400
    assert "Unsupported platform" in response.json()["detail"]


def test_repurpose_rejects_empty_platform_before_calling_claude(monkeypatch):
    """An empty `platform` string ("") is still a valid str, so without a
    min_length check it would slip past Pydantic and only get caught deep
    in main.py's unsupported-platform check -- a confusing 400 ("Unsupported
    platform ''") that reads like a typo got misreported. Rejecting it here
    instead gives a clear 422 at the same validation layer that already
    catches an empty script, before call_claude ever runs."""
    def fail_if_called(system_prompt, user_content):
        raise AssertionError("call_claude should never run for an empty platform")

    monkeypatch.setattr("repurposer.main.call_claude", fail_if_called)

    response = client.post("/repurpose", json={"script": "some script", "platform": ""})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_short"
    assert response.json()["detail"][0]["loc"] == ["body", "platform"]


def test_repurpose_all_rejects_empty_platform_in_subset_before_calling_claude(monkeypatch):
    """Same guard applies to every entry inside /repurpose-all's `platforms`
    list, not just the single `platform` field on /repurpose -- a stray
    empty string in the subset is caught at the same layer, before any
    platform in the fan-out spends a token."""
    def fail_if_called(system_prompt, user_content):
        raise AssertionError("call_claude should never run when the platform list has an empty entry")

    monkeypatch.setattr("repurposer.main.call_claude", fail_if_called)

    response = client.post("/repurpose-all", json={"script": "some script", "platforms": ["x", ""]})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_short"
    assert response.json()["detail"][0]["loc"] == ["body", "platforms", 1]


def test_repurpose_rejects_empty_script_before_calling_claude(monkeypatch):
    """An empty paste box should never reach Claude -- Pydantic's min_length
    rejects it with a 422 before the endpoint body (and call_claude) ever
    runs. Patches call_claude with a spy that fails the test if it's
    called at all, so this proves no token gets spent, not just that the
    status code looks right."""
    def fail_if_called(system_prompt, user_content):
        raise AssertionError("call_claude should never run for an empty script")

    monkeypatch.setattr("repurposer.main.call_claude", fail_if_called)

    response = client.post("/repurpose", json={"script": "", "platform": "x"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_short"


def test_repurpose_rejects_oversized_script_before_calling_claude(monkeypatch):
    """A script past config.MAX_SCRIPT_LENGTH is rejected with a 422 before
    any API call is spent -- same no-token-spend guarantee as the empty
    case above, just at the other end of the length range."""
    from repurposer import config

    def fail_if_called(system_prompt, user_content):
        raise AssertionError("call_claude should never run for an oversized script")

    monkeypatch.setattr("repurposer.main.call_claude", fail_if_called)

    too_long = "a" * (config.MAX_SCRIPT_LENGTH + 1)
    response = client.post("/repurpose", json={"script": too_long, "platform": "x"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"


def test_repurpose_all_rejects_oversized_script_before_calling_claude(monkeypatch):
    """Same guard applies to the fan-out endpoint -- without this, one
    oversized paste would have multiplied the wasted cost by every
    platform in the fan-out instead of being rejected once, for free."""
    from repurposer import config

    def fail_if_called(system_prompt, user_content):
        raise AssertionError("call_claude should never run for an oversized script")

    monkeypatch.setattr("repurposer.main.call_claude", fail_if_called)

    too_long = "a" * (config.MAX_SCRIPT_LENGTH + 1)
    response = client.post("/repurpose-all", json={"script": too_long})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_long"


def test_repurpose_accepts_script_exactly_at_the_length_cap(monkeypatch):
    """The boundary itself must still work -- a script exactly at
    MAX_SCRIPT_LENGTH is valid, not rejected. Only *over* the cap is."""
    from repurposer import config

    fake_thread = "1/ right at the edge and still fine."
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_thread)

    exactly_at_cap = "a" * config.MAX_SCRIPT_LENGTH
    response = client.post("/repurpose", json={"script": exactly_at_cap, "platform": "x"})

    assert response.status_code == 200


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


def test_repurpose_returns_plain_text_for_tiktok(monkeypatch):
    """TikTok is a plain-text platform like X and LinkedIn -- it's a spoken
    script, not structured data, so it reuses the same `content` shape."""
    fake_script = "[hook] AI agents are the thing nobody explains right. Here's why that matters..."
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_script)

    response = client.post("/repurpose", json={"script": "A script about AI agents.", "platform": "tiktok"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"platform": "tiktok", "content": fake_script, "carousel": None}


def test_repurpose_returns_plain_text_for_newsletter(monkeypatch):
    """Newsletter is also plain text -- one section of the weekly digest,
    not a list of discrete pieces, so there's no reason to add a new model."""
    fake_section = "AI Agents, Explained\n\nHere's what actually matters this week..."
    monkeypatch.setattr("repurposer.main.call_claude", lambda system_prompt, user_content: fake_section)

    response = client.post("/repurpose", json={"script": "A script about AI agents.", "platform": "newsletter"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"platform": "newsletter", "content": fake_section, "carousel": None}


def test_repurpose_all_returns_every_platform(monkeypatch):
    """/repurpose-all fans out to all five platforms in one call and reuses
    the same _build_response path, so instagram still comes back as a typed
    carousel while the other four come back as plain text."""
    instagram_json = json.dumps(
        {
            "caption": "AI agents in 5 slides.",
            "slides": ["hook", "problem", "idea", "how it works", "join the Discord"],
        }
    )

    def fake_call_claude(system_prompt, user_content):
        # Use the system prompt itself to figure out which platform is being
        # asked for, so each platform in the fan-out gets a distinct fake
        # response -- proving all five actually got called, not just one.
        if "Instagram carousel" in system_prompt:
            return instagram_json
        if "TikTok" in system_prompt:
            return "tiktok script text"
        if "LinkedIn" in system_prompt:
            return "linkedin post text"
        if "Email newsletter" in system_prompt:
            return "newsletter section text"
        return "x thread text"

    monkeypatch.setattr("repurposer.main.call_claude", fake_call_claude)

    response = client.post("/repurpose-all", json={"script": "A long YouTube script about AI agents."})

    assert response.status_code == 200
    body = response.json()
    results = body["results"]
    assert len(results) == 5

    by_platform = {r["platform"]: r for r in results}
    assert set(by_platform.keys()) == {"x", "linkedin", "instagram", "tiktok", "newsletter"}
    assert by_platform["x"]["content"] == "x thread text"
    assert by_platform["linkedin"]["content"] == "linkedin post text"
    assert by_platform["tiktok"]["content"] == "tiktok script text"
    assert by_platform["newsletter"]["content"] == "newsletter section text"
    assert by_platform["instagram"]["content"] is None
    assert len(by_platform["instagram"]["carousel"]["slides"]) == 5


def test_repurpose_all_respects_platform_subset(monkeypatch):
    """Passing `platforms` narrows the fan-out to just those platforms --
    the toggle UI's whole point is letting someone skip platforms they don't
    want, so the backend must only call Claude for the ones asked for."""
    calls = []

    def fake_call_claude(system_prompt, user_content):
        calls.append(system_prompt)
        return "some text"

    monkeypatch.setattr("repurposer.main.call_claude", fake_call_claude)

    response = client.post(
        "/repurpose-all",
        json={"script": "A script about AI agents.", "platforms": ["x", "linkedin"]},
    )

    assert response.status_code == 200
    body = response.json()
    results = body["results"]
    assert len(results) == 2
    assert {r["platform"] for r in results} == {"x", "linkedin"}
    # Proves only 2 Claude calls happened, not all 5.
    assert len(calls) == 2


def test_repurpose_all_defaults_to_every_platform_when_platforms_omitted(monkeypatch):
    """Existing callers that never send `platforms` must keep getting the
    original "all five" behavior -- this field is additive, not breaking."""
    instagram_json = json.dumps({"caption": "caption text", "slides": ["s1", "s2", "s3", "s4", "s5"]})

    def fake_call_claude(system_prompt, user_content):
        if "Instagram carousel" in system_prompt:
            return instagram_json
        return "some platform text"

    monkeypatch.setattr("repurposer.main.call_claude", fake_call_claude)

    response = client.post("/repurpose-all", json={"script": "A script about AI agents."})

    assert response.status_code == 200
    assert len(response.json()["results"]) == 5


def test_repurpose_all_rejects_unsupported_platform_in_subset():
    response = client.post(
        "/repurpose-all",
        json={"script": "some script", "platforms": ["x", "facebook"]},
    )

    assert response.status_code == 400
    assert "Unsupported platform" in response.json()["detail"]
    assert "facebook" in response.json()["detail"]


def test_repurpose_all_fails_loudly_when_api_key_missing(monkeypatch):
    """Same honesty rule applies to the fan-out: if the key is missing, this
    must not quietly return a partial list of whichever platforms happened
    to run first -- it has to fail loudly, just like /repurpose does."""
    from repurposer.claude_client import MissingApiKeyError

    def raise_missing_key(system_prompt, user_content):
        raise MissingApiKeyError("ANTHROPIC_API_KEY is not set.")

    monkeypatch.setattr("repurposer.main.call_claude", raise_missing_key)

    response = client.post("/repurpose-all", json={"script": "some script"})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY is not set" in response.json()["detail"]


def test_repurpose_surfaces_claude_api_error_with_its_own_status_code(monkeypatch):
    """When the key is set but Claude's API itself rejects/fails the call
    (bad key, Anthropic's rate limit, their outage), the endpoint must map
    it to a clear HTTP error using the status code the error carries --
    never an unhandled 500 with a raw stack trace."""
    from repurposer.claude_client import ClaudeApiError

    def raise_claude_api_error(system_prompt, user_content):
        raise ClaudeApiError("Claude rejected the API key as invalid.", status_code=502)

    monkeypatch.setattr("repurposer.main.call_claude", raise_claude_api_error)

    response = client.post("/repurpose", json={"script": "some script", "platform": "x"})

    assert response.status_code == 502
    assert "Claude rejected the API key as invalid" in response.json()["detail"]


def test_repurpose_all_surfaces_claude_api_error_with_its_own_status_code(monkeypatch):
    """Same mapping applies to the fan-out endpoint -- a Claude-side failure
    on any platform in the loop must fail loudly with the right status code,
    not a generic 500."""
    from repurposer.claude_client import ClaudeApiError

    def raise_claude_api_error(system_prompt, user_content):
        raise ClaudeApiError("Couldn't reach the Claude API -- a network problem.", status_code=503)

    monkeypatch.setattr("repurposer.main.call_claude", raise_claude_api_error)

    response = client.post("/repurpose-all", json={"script": "some script", "platforms": ["x"]})

    assert response.status_code == 503
    assert "Couldn't reach the Claude API" in response.json()["detail"]


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
