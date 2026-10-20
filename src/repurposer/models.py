"""Pydantic models -- the output shape is pinned here from day one."""

from typing import Annotated, List, Optional

from pydantic import BaseModel, Field

from . import config

# Shared across both request models so a oversized-script rejection is
# worded the same way everywhere, and the limit itself lives in one place
# (config.py) instead of being copy-pasted as a bare number.
_SCRIPT_FIELD_KWARGS = dict(
    min_length=1,
    max_length=config.MAX_SCRIPT_LENGTH,
    description=(
        "The source script or long-form text to repurpose. "
        f"Max {config.MAX_SCRIPT_LENGTH:,} characters."
    ),
)

# A non-empty platform name. Used for the single `platform` field on
# RepurposeRequest and for every entry in RepurposeAllRequest.platforms --
# without this, an empty string ("") slips past Pydantic (it's still a
# valid `str`) and only gets caught deep in main.py's "unsupported platform"
# check, where the resulting message ("Unsupported platform ''") reads like
# a typo got misreported rather than an empty field. Catching it here gives
# a clear 422 ("String should have at least 1 character") at the same layer
# that already catches an empty script, instead of a confusing 400 later.
_NonEmptyPlatform = Annotated[str, Field(min_length=1)]


class RepurposeRequest(BaseModel):
    script: str = Field(..., **_SCRIPT_FIELD_KWARGS)
    platform: _NonEmptyPlatform = Field(
        ..., description="Target platform. Supports: x, linkedin, instagram, tiktok, newsletter"
    )


class RepurposeAllRequest(BaseModel):
    """Request shape for /repurpose-all. `platforms` is optional and defaults
    to every supported platform when omitted or empty -- so existing callers
    (and the original "always all five" behavior) keep working unchanged.
    Pass a subset to only fan out to the platforms the caller actually wants."""

    script: str = Field(..., **_SCRIPT_FIELD_KWARGS)
    platforms: Optional[List[_NonEmptyPlatform]] = Field(
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
