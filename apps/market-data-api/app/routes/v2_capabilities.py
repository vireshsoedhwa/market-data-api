"""V2 discovery endpoints — capabilities and tool definitions."""

from fastapi import APIRouter, Depends

from app.dependencies import verify_api_key
from app.schemas.v2 import (
    AuthenticationInfo,
    CapabilitiesResponse,
    DataFreshnessDetail,
    RateLimitsInfo,
    ToolDefinition,
    ToolFunction,
    ToolParameterProperty,
    ToolParameters,
    ToolsResponse,
)
from app.settings import settings

router = APIRouter(prefix="/v2", tags=["discovery"], dependencies=[Depends(verify_api_key)])


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities():
    """Return a machine-readable manifest of API capabilities."""
    return CapabilitiesResponse(
        version=settings.api_version,
        endpoints=["quotes", "history", "symbols", "refresh"],
        max_batch_size=settings.rate_limit_batch_max_symbols,
        supported_timeframes=["1d", "1wk", "1mo"],
        supported_exchanges=["NYSE", "NASDAQ", "TSX"],
        data_freshness={
            "latest_price": DataFreshnessDetail(
                typical_delay="15min",
                max_staleness="24h",
            ),
            "daily_history": DataFreshnessDetail(
                typical_delay="EOD",
                coverage_target=0.95,
                lag="EOD",
            ),
        },
        rate_limits=RateLimitsInfo(
            requests_per_minute=settings.rate_limit_requests_per_minute,
            batch_max_symbols=settings.rate_limit_batch_max_symbols,
        ),
        authentication=AuthenticationInfo(),
    )


@router.get("/tools", response_model=ToolsResponse)
async def get_tools():
    """Return tool schemas in OpenAI function-calling format."""
    return ToolsResponse(
        tools=[
            ToolDefinition(
                function=ToolFunction(
                    name="get_latest_price",
                    description="Get the most recent price for a stock symbol",
                    parameters=ToolParameters(
                        properties={
                            "symbol": ToolParameterProperty(
                                type="string",
                                description="Ticker symbol (e.g. AAPL)",
                            ),
                            "exchange": ToolParameterProperty(
                                type="string",
                                description="Optional exchange filter",
                            ),
                        },
                        required=["symbol"],
                    ),
                ),
            ),
            ToolDefinition(
                function=ToolFunction(
                    name="get_daily_history",
                    description="Get OHLCV daily bars for a symbol over a date range",
                    parameters=ToolParameters(
                        properties={
                            "symbol": ToolParameterProperty(
                                type="string",
                                description="Ticker symbol (e.g. AAPL)",
                            ),
                            "start_date": ToolParameterProperty(
                                type="string",
                                description="Start date in YYYY-MM-DD format",
                            ),
                            "end_date": ToolParameterProperty(
                                type="string",
                                description="End date in YYYY-MM-DD format",
                            ),
                        },
                        required=["symbol", "start_date", "end_date"],
                    ),
                ),
            ),
            ToolDefinition(
                function=ToolFunction(
                    name="search_symbols",
                    description="Search for stock symbols matching a query string",
                    parameters=ToolParameters(
                        properties={
                            "query": ToolParameterProperty(
                                type="string",
                                description="Search query (e.g. 'nvidia' or 'NVDA')",
                            ),
                        },
                        required=["query"],
                    ),
                ),
            ),
            ToolDefinition(
                function=ToolFunction(
                    name="refresh_data",
                    description="Request a fresh data pull for one or more symbols",
                    parameters=ToolParameters(
                        properties={
                            "symbols": ToolParameterProperty(
                                type="array",
                                description="List of ticker symbols to refresh",
                            ),
                        },
                        required=["symbols"],
                    ),
                ),
            ),
        ]
    )
