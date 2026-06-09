from datetime import date

from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.router.provider_router import get_daily_history
from app.schemas.history import BatchHistoryRequest, HistoryResponse

router = APIRouter(prefix="/v1/history", tags=["history"], dependencies=[Depends(verify_api_key)])


@router.get("/{symbol}", response_model=HistoryResponse)
async def get_history(
    symbol: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    timeframe: str = Query(default="1d"),
):
    return await get_daily_history(symbol, start_date, end_date, timeframe)


@router.post("/batch", response_model=list[HistoryResponse])
async def get_history_batch(request: BatchHistoryRequest):
    results: list[HistoryResponse] = []

    for sym in request.symbols:
        result = await get_daily_history(
            sym, request.start_date, request.end_date, request.timeframe
        )
        results.append(result)

    return results
