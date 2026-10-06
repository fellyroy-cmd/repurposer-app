"""FastAPI app. Endpoints: /health and /repurpose (x, linkedin, instagram)."""

import json

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from . import config
from .claude_client import MissingApiKeyError, call_claude
from .models import HealthResponse, InstagramCarousel, RepurposeRequest, RepurposeResponse

app = FastAPI(
    title="Repurposer App",
    description="Paste a script, get it rewritten for another platform in Dara's brand voice.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def _build_response(platform: str, raw_content: str) -> RepurposeResponse:
    """Turns Claude's raw text into the typed response shape for this
    platform. Structured platforms (instagram) must come back as valid JSON
    matching InstagramCarousel -- if Claude returns something else, this
    fails loudly with a 502 instead of silently passing junk through."""
    if platform not in config.STRUCTURED_PLATFORMS:
        return RepurposeResponse(platform=platform, content=raw_content)

    try:
        parsed = json.loads(raw_content)
        carousel = InstagramCarousel.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Claude's response for platform '{platform}' wasn't valid structured "
                f"JSON matching the expected shape. Raw error: {exc}"
            ),
        ) from exc

    return RepurposeResponse(platform=platform, carousel=carousel)


@app.post("/repurpose", response_model=RepurposeResponse)
def repurpose(req: RepurposeRequest) -> RepurposeResponse:
    if req.platform not in config.SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform '{req.platform}'. Supported so far: {config.SUPPORTED_PLATFORMS}",
        )

    system_prompt = config.get_system_prompt(req.platform)

    try:
        raw_content = call_claude(system_prompt, req.script)
    except MissingApiKeyError as exc:
        # Fail loudly -- no fake demo mode, per the project's honesty rule.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _build_response(req.platform, raw_content)
