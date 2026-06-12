"""Structured error handling for the market-data-api.

Defines error codes, custom exceptions, and a global exception handler
that returns the v2 error envelope format.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


# Standard error codes
SYMBOL_NOT_FOUND = "SYMBOL_NOT_FOUND"
PROVIDER_EXHAUSTED = "PROVIDER_EXHAUSTED"
RATE_LIMITED = "RATE_LIMITED"
INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
INVALID_SYMBOL = "INVALID_SYMBOL"
BATCH_TOO_LARGE = "BATCH_TOO_LARGE"
INTERNAL_ERROR = "INTERNAL_ERROR"


class MarketDataError(Exception):
    """Base exception for market-data-api errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        symbol: str | None = None,
        retry_after_seconds: int | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.symbol = symbol
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers that return the v2 error envelope."""

    @app.exception_handler(MarketDataError)
    async def market_data_error_handler(request: Request, exc: MarketDataError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "symbol": exc.symbol,
                    "retry_after_seconds": exc.retry_after_seconds,
                }
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        # If the detail is already a dict with our error shape, pass it through
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.detail,
            )
        # Otherwise wrap it in our envelope
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": _status_to_code(exc.status_code),
                    "message": str(exc.detail),
                    "symbol": None,
                    "retry_after_seconds": None,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": INTERNAL_ERROR,
                    "message": "An internal error occurred",
                    "symbol": None,
                    "retry_after_seconds": None,
                }
            },
        )


def _status_to_code(status_code: int) -> str:
    """Map HTTP status codes to our error codes."""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
        429: RATE_LIMITED,
    }
    return mapping.get(status_code, INTERNAL_ERROR)
