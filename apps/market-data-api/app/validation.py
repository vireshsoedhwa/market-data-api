"""Input validation helpers for v2 endpoints.

Provides strict validators for:
- Symbol parameters (regex)
- Date range parameters (format, range limits)
- Batch sizes (server-side cap)
"""

import re
from datetime import date, timedelta

from fastapi import HTTPException, status

from app.settings import settings

# Symbol must be 1-10 uppercase alphanumeric characters, dots, or hyphens
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,10}$")


def validate_symbol(symbol: str) -> str:
    """Validate and normalize a ticker symbol. Raises 400 on invalid input."""
    symbol = symbol.upper().strip()
    if not SYMBOL_PATTERN.match(symbol):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_SYMBOL",
                    "message": f"Symbol must match pattern {SYMBOL_PATTERN.pattern}",
                    "symbol": symbol,
                    "retry_after_seconds": None,
                }
            },
        )
    return symbol


def validate_date_range(start_date: date, end_date: date) -> tuple[date, date]:
    """Validate that a date range is sensible. Raises 400 on invalid input."""
    today = date.today()
    max_future = today + timedelta(days=1)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_DATE_RANGE",
                    "message": "start_date must be before or equal to end_date",
                    "retry_after_seconds": None,
                }
            },
        )

    if end_date > max_future:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_DATE_RANGE",
                    "message": f"end_date cannot be more than one day in the future (max: {max_future})",
                    "retry_after_seconds": None,
                }
            },
        )

    return start_date, end_date


def validate_batch_symbols(symbols: list[str]) -> list[str]:
    """Validate and normalize a list of symbols for batch endpoints."""
    max_size = settings.rate_limit_batch_max_symbols
    if len(symbols) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "BATCH_TOO_LARGE",
                    "message": f"Batch size {len(symbols)} exceeds maximum of {max_size}",
                    "retry_after_seconds": None,
                }
            },
        )
    return [validate_symbol(s) for s in symbols]
