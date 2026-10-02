import os

import pytest

from repurposer.claude_client import MissingApiKeyError, call_claude


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
