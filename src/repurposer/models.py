"""Pydantic models -- the output shape is pinned here from day one."""

from pydantic import BaseModel, Field


class RepurposeRequest(BaseModel):
    script: str = Field(..., min_length=1, description="The source script or long-form text to repurpose.")
    platform: str = Field(..., description="Target platform. Week 1 supports: x")


class RepurposeResponse(BaseModel):
    platform: str
    content: str


class HealthResponse(BaseModel):
    status: str
