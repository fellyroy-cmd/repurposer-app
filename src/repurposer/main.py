"""FastAPI app. Two endpoints this week: /health and /repurpose (X only)."""

from fastapi import FastAPI, HTTPException

from . import config
from .claude_client import MissingApiKeyError, call_claude
from .models import HealthResponse, RepurposeRequest, RepurposeResponse

app = FastAPI(
    title="Repurposer App",
    description="Paste a script, get it rewritten for another platform in Dara's brand voice.",
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/repurpose", response_model=RepurposeResponse)
def repurpose(req: RepurposeRequest) -> RepurposeResponse:
    if req.platform not in config.SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform '{req.platform}'. Supported this week: {config.SUPPORTED_PLATFORMS}",
        )

    system_prompt = config.get_system_prompt(req.platform)

    try:
        content = call_claude(system_prompt, req.script)
    except MissingApiKeyError as exc:
        # Fail loudly -- no fake demo mode, per the project's honesty rule.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RepurposeResponse(platform=req.platform, content=content)
