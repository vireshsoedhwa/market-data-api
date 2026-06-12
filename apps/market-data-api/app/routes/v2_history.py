"""V2 history endpoints with response envelope and input validation."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.router.provider_router import get_daily_history
from app.schemas.v2 import ResponseEnvelope, ResponseMeta
from app.validation import validate_batch_symbols, validate_date_range, validate_symbol

router = APIRouter(prefix="/v2/history", tags=["history"], dependencies=[Depends(verify_api_key)])


@router.get("/{symbol}")
async def get_history(
    symbol: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    timeframe: str = Query(default="1d"),
):
    symbol = validate_symbol(symbol)
    validate_date_range(start_date, end_date)

    result = await get_daily_history(symbol, start_date, end_date, timeframe)
    return ResponseEnvelope(
        request={
            "symbol": symbol,
            "endpoint": "history",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "timeframe": timeframe,
        },
        data=result.model_dump(mode="json"),
        meta=ResponseMeta(
            provider=result.provider_chain_used[0] if result.provider_chain_used else None,
            source_type="provider",
            confidence="high" if result.coverage and result.coverage > 0.9 else "low",
            as_of=datetime.now(timezone.utc),
            warnings=result.warnings,
        ),
    ).model_dump(mode="json")


@router.post("/batch")
async def get_history_batch(request: dict):
    raw_symbols = request.get("symbols", [])
    symbols = validate_batch_symbols(raw_symbols)
    start_date = date.fromisoformat(request["start_date"])
    end_date = date.fromisoformat(request["end_date"])
    timeframe = request.get("timeframe", "1d")

    validate_date_range(start_date, end_date)

    results = []
    for sym in symbols:
        result = await get_daily_history(sym, start_date, end_date, timeframe)
        results.append(result.model_dump(mode="json"))

    return ResponseEnvelope(
        request={
            "symbols": symbols,
            "endpoint": "history/batch",
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        data=results,
        meta=ResponseMeta(
            as_of=datetime.now(timezone.utc),
            warnings=[],
        ),
    ).model_dump(mode="json")
