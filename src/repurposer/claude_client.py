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


class ClaudeApiError(RuntimeError):
    """Raised when the Anthropic API itself rejects or fails a request --
    bad key, Anthropic-side rate limit, network/connection failure, or a
    server-side error. Wraps the SDK's exception in a message that's safe to
    show a user: never the raw key, never raw SDK/httpx internals (request
    objects, response bodies) that could leak something unintended."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _wrap_sdk_error(exc: anthropic.AnthropicError) -> ClaudeApiError:
    """Turns any Anthropic SDK exception into a ClaudeApiError with a clear,
    safe-to-display message. Only `.message`/`.status_code` are read off the
    SDK exception (never `.body` or `.request`) -- the SDK's own message text
    never contains the API key, but the raw request/response objects could
    carry more than we want to echo back to a caller."""
    if isinstance(exc, anthropic.AuthenticationError):
        return ClaudeApiError(
            "Claude rejected the API key as invalid. Check ANTHROPIC_API_KEY in "
            ".env -- this is a bad/expired key, not a missing one.",
            status_code=502,
        )
    if isinstance(exc, anthropic.RateLimitError):
        return ClaudeApiError(
            "Claude's API rate limit was hit (Anthropic's limit on your account, "
            "not this app's). Wait a moment and try again.",
            status_code=502,
        )
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return ClaudeApiError(
            "Couldn't reach the Claude API -- a network or timeout problem, not "
            "a code bug. Try again in a moment.",
            status_code=503,
        )
    if isinstance(exc, anthropic.APIStatusError):
        return ClaudeApiError(
            f"Claude's API returned an error (status {exc.status_code}): {exc.message}",
            status_code=502,
        )
    # Catch-all for any other AnthropicError subclass the SDK might raise.
    return ClaudeApiError(f"Claude API call failed: {exc}", status_code=502)


def call_claude(system_prompt: str, user_content: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your "
            "real key -- this app never fakes a response, so there is nothing to "
            "return until a key is configured."
        )

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AnthropicError as exc:
        # Fail loudly with a safe message -- never let a raw SDK exception
        # (which could carry request/response internals) reach the caller
        # unhandled, and never swallow it into a fake response either.
        raise _wrap_sdk_error(exc) from exc

    # Newer models can put a "thinking" block before the answer, so content[0]
    # isn't always the text. Join every text block instead of trusting position.
    text = "".join(b.text for b in message.content if b.type == "text" and b.text)
    if not text:
        raise ClaudeApiError("Claude returned no text for this request. Try again.", status_code=502)
    return text
