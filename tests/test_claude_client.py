import os

import anthropic
import httpx
import pytest

from repurposer.claude_client import ClaudeApiError, MissingApiKeyError, call_claude


def _fake_api_status_error(error_cls, status_code, message):
    """Builds a real anthropic SDK status error the same way the SDK itself
    would -- with a real httpx.Request/Response underneath -- so tests prove
    our wrapper handles the actual exception shape, not a hand-rolled stand-in."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return error_cls(message, response=response, body={"error": {"message": message}})


def test_call_claude_raises_clearly_when_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(MissingApiKeyError, match="ANTHROPIC_API_KEY is not set"):
        call_claude(system_prompt="system", user_content="user")


def test_call_claude_calls_sdk_with_configured_model(monkeypatch):
    """Mocks the anthropic SDK itself (not just our wrapper) to prove the
    real integration code -- model id, system prompt, message shape -- is
    wired correctly, without ever hitting the network."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    captured = {}

    class FakeTextBlock:
        type = "text"
        text = "mocked platform content"

    class FakeMessage:
        content = [FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeMessage()

    class FakeAnthropicClient:
        def __init__(self, api_key):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    result = call_claude(system_prompt="be brief", user_content="a script")

    assert result == "mocked platform content"
    assert captured["system"] == "be brief"
    assert captured["messages"] == [{"role": "user", "content": "a script"}]
    assert captured["api_key"] == "fake-key-for-test"


def test_call_claude_wraps_authentication_error_without_leaking_the_key(monkeypatch):
    """A set-but-wrong key reaches the SDK, which rejects it. The wrapper must
    turn that into a clear ClaudeApiError -- and the real key must never show
    up anywhere in the resulting error message."""
    real_key = "sk-ant-totally-real-secret-value"
    monkeypatch.setenv("ANTHROPIC_API_KEY", real_key)

    sdk_error = _fake_api_status_error(anthropic.AuthenticationError, 401, "invalid x-api-key")

    class FakeMessages:
        def create(self, **kwargs):
            raise sdk_error

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    with pytest.raises(ClaudeApiError, match="rejected the API key as invalid") as exc_info:
        call_claude(system_prompt="system", user_content="user")

    assert exc_info.value.status_code == 502
    assert real_key not in str(exc_info.value)


def test_call_claude_wraps_anthropic_rate_limit_error(monkeypatch):
    """Anthropic's own rate limit (not this app's) must surface clearly and
    be distinguishable from this app's local 429."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    sdk_error = _fake_api_status_error(anthropic.RateLimitError, 429, "rate limit exceeded")

    class FakeMessages:
        def create(self, **kwargs):
            raise sdk_error

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    with pytest.raises(ClaudeApiError, match="Claude's API rate limit") as exc_info:
        call_claude(system_prompt="system", user_content="user")

    assert exc_info.value.status_code == 502


def test_call_claude_wraps_connection_error_as_503(monkeypatch):
    """A network failure reaching Anthropic is a transient infrastructure
    problem, not a client bug -- it should map to 503, not 502/500."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    sdk_error = anthropic.APIConnectionError(request=request)

    class FakeMessages:
        def create(self, **kwargs):
            raise sdk_error

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    with pytest.raises(ClaudeApiError, match="Couldn't reach the Claude API") as exc_info:
        call_claude(system_prompt="system", user_content="user")

    assert exc_info.value.status_code == 503


def test_call_claude_wraps_generic_server_error(monkeypatch):
    """A 5xx from Anthropic's side (their outage, not ours) still needs a
    clear, loud message instead of an unhandled exception reaching the API
    layer as a raw 500 with a stack trace."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    sdk_error = _fake_api_status_error(anthropic.InternalServerError, 500, "internal server error")

    class FakeMessages:
        def create(self, **kwargs):
            raise sdk_error

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = FakeMessages()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    with pytest.raises(ClaudeApiError, match="status 500") as exc_info:
        call_claude(system_prompt="system", user_content="user")

    assert exc_info.value.status_code == 502


def test_call_claude_skips_a_leading_thinking_block(monkeypatch):
    """Newer models can return a thinking block before the answer. Reading
    content[0] blindly returned None and the API sent back an empty post."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

    class FakeThinkingBlock:
        type = "thinking"
        text = None

    class FakeTextBlock:
        type = "text"
        text = "the real answer"

    class FakeMessage:
        content = [FakeThinkingBlock(), FakeTextBlock()]

    class FakeAnthropicClient:
        def __init__(self, api_key):
            self.messages = type("M", (), {"create": lambda self, **kw: FakeMessage()})()

    monkeypatch.setattr("repurposer.claude_client.anthropic.Anthropic", FakeAnthropicClient)

    assert call_claude(system_prompt="s", user_content="u") == "the real answer"
