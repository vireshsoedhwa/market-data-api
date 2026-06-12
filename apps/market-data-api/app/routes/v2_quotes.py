"""V2 quotes endpoints with response envelope and input validation."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.router.provider_router import get_latest_price
from app.schemas.quotes import QuoteResponse
from app.schemas.v2 import ResponseEnvelope, ResponseMeta
from app.validation import validate_batch_symbols, validate_symbol

router = APIRouter(prefix="/v2/quotes", tags=["quotes"], dependencies=[Depends(verify_api_key)])


def _wrap_quote(quote: QuoteResponse, endpoint: str = "quotes") -> dict:
    """Wrap a QuoteResponse in the v2 response envelope."""
    return ResponseEnvelope(
        request={"symbol": quote.symbol, "endpoint": endpoint},
        data=quote.model_dump(mode="json"),
        meta=ResponseMeta(
            provider=quote.provider,
            source_type=quote.source_type,
            confidence=quote.confidence,
            as_of=quote.as_of,
            is_delayed=quote.is_delayed,
            delay_minutes=quote.delay_minutes,
            warnings=quote.warnings,
        ),
    ).model_dump(mode="json")


@router.get("/{symbol}")
async def get_quote(symbol: str, exchange: str | None = Query(default=None)):
    symbol = validate_symbol(symbol)
    quote = await get_latest_price(symbol, exchange)
    return _wrap_quote(quote)


@router.post("/batch")
async def get_quotes_batch(request: dict):
    raw_symbols = request.get("symbols", [])
    symbols = validate_batch_symbols(raw_symbols)

    results: list[dict] = []
    errors: list[dict] = []

    for sym in symbols:
        try:
            quote = await get_latest_price(sym)
            results.append(quote.model_dump(mode="json"))
        except Exception as exc:
            errors.append({"symbol": sym, "error": str(exc)})

    return ResponseEnvelope(
        request={"symbols": symbols, "endpoint": "quotes/batch"},
        data={"quotes": results, "errors": errors},
        meta=ResponseMeta(
            as_of=datetime.now(timezone.utc),
            warnings=[],
        ),
    ).model_dump(mode="json")
