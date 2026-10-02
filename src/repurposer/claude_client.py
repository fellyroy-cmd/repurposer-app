"""
Thin wrapper around the Anthropic SDK. Kept in its own module so tests can
patch `call_claude` directly instead of mocking the SDK's internals -- that's
what makes `pytest` green with zero API key and zero real network calls.
"""

import os

import anthropic

from . import config


class MissingApiKeyError(RuntimeError):
    """Raised when ANTHROPIC_API_KEY isn't set. Caught by the API layer and
    turned into a clear, loud HTTP error -- never a silent fake response."""


def call_claude(system_prompt: str, user_content: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your "
            "real key -- this app never fakes a response, so there is nothing to "
            "return until a key is configured."
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text
