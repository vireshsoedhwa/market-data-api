"""V2 API schemas — error envelope, response wrapper, capabilities, and tool definitions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    symbol: str | None = None
    retry_after_seconds: int | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Response meta
# ---------------------------------------------------------------------------

class ResponseMeta(BaseModel):
    provider: str | None = None
    source_type: str | None = None
    confidence: str | None = None
    as_of: datetime | None = None
    is_delayed: bool | None = None
    delay_minutes: int | None = None
    warnings: list[str] = Field(default_factory=list)


class ResponseEnvelope(BaseModel):
    request: dict[str, Any]
    data: Any
    meta: ResponseMeta


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class DataFreshnessDetail(BaseModel):
    typical_delay: str
    max_staleness: str | None = None
    coverage_target: float | None = None
    lag: str | None = None


class RateLimitsInfo(BaseModel):
    requests_per_minute: int
    batch_max_symbols: int


class AuthenticationInfo(BaseModel):
    type: str = "bearer"
    header: str = "Authorization"


class CapabilitiesResponse(BaseModel):
    version: str
    endpoints: list[str]
    max_batch_size: int
    supported_timeframes: list[str]
    supported_exchanges: list[str]
    data_freshness: dict[str, DataFreshnessDetail]
    rate_limits: RateLimitsInfo
    authentication: AuthenticationInfo


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

class ToolParameterProperty(BaseModel):
    type: str
    description: str


class ToolParameters(BaseModel):
    type: str = "object"
    properties: dict[str, ToolParameterProperty]
    required: list[str] = Field(default_factory=list)


class ToolFunction(BaseModel):
    name: str
    description: str
    parameters: ToolParameters


class ToolDefinition(BaseModel):
    type: str = "function"
    function: ToolFunction


class ToolsResponse(BaseModel):
    tools: list[ToolDefinition]
