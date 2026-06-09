from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.router.provider_router import get_latest_price
from app.schemas.quotes import BatchQuoteRequest, BatchQuoteResponse, QuoteResponse

router = APIRouter(prefix="/v1/quotes", tags=["quotes"], dependencies=[Depends(verify_api_key)])


@router.get("/{symbol}", response_model=QuoteResponse)
async def get_quote(symbol: str, exchange: str | None = Query(default=None)):
    return await get_latest_price(symbol, exchange)


@router.post("/batch", response_model=BatchQuoteResponse)
async def get_quotes_batch(request: BatchQuoteRequest):
    quotes: list[QuoteResponse] = []
    errors: list[dict] = []

    for sym in request.symbols:
        try:
            quote = await get_latest_price(sym)
            quotes.append(quote)
        except Exception as exc:
            errors.append({"symbol": sym, "error": str(exc)})

    return BatchQuoteResponse(quotes=quotes, errors=errors)
