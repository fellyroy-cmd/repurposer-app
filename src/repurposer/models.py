"""Pydantic models -- the output shape is pinned here from day one."""

from typing import List, Optional

from pydantic import BaseModel, Field


class RepurposeRequest(BaseModel):
    script: str = Field(..., min_length=1, description="The source script or long-form text to repurpose.")
    platform: str = Field(
        ..., description="Target platform. Supports: x, linkedin, instagram, tiktok, newsletter"
    )


class RepurposeAllRequest(BaseModel):
    """Request shape for /repurpose-all. `platforms` is optional and defaults
    to every supported platform when omitted or empty -- so existing callers
    (and the original "always all five" behavior) keep working unchanged.
    Pass a subset to only fan out to the platforms the caller actually wants."""

    script: str = Field(..., min_length=1, description="The source script or long-form text to repurpose.")
    platforms: Optional[List[str]] = Field(
        default=None,
        description="Subset of platforms to generate. Omit or leave empty for all supported platforms.",
    )


class InstagramCarousel(BaseModel):
    """Structured shape for an IG carousel -- a list of slides plus the
    caption that goes under the post, instead of one wall of text."""

    caption: str
    slides: List[str] = Field(..., min_length=1)


class RepurposeResponse(BaseModel):
    platform: str
    # Plain-text platforms (x, linkedin) fill `content`. Structured platforms
    # (instagram) fill `carousel` instead and leave `content` empty -- this
    # keeps the API honest about which platforms return typed data vs text.
    content: Optional[str] = None
    carousel: Optional[InstagramCarousel] = None


class RepurposeAllResponse(BaseModel):
    """Fan-out response for /repurpose-all -- one entry per platform that
    actually succeeded. Added once all five platforms are wired up."""

    results: List[RepurposeResponse]


class HealthResponse(BaseModel):
    status: str
