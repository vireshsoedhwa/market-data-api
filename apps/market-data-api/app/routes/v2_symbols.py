"""V2 symbols endpoints with response envelope and input validation."""

from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.schemas.v2 import ResponseEnvelope, ResponseMeta
from app.validation import validate_symbol

router = APIRouter(prefix="/v2/symbols", tags=["symbols"], dependencies=[Depends(verify_api_key)])


@router.get("/search")
async def search_symbols(query: str = Query(..., min_length=1)):
    """
    Search for symbols matching the query string.

    TODO: Implement provider-backed symbol search.
    """
    return ResponseEnvelope(
        request={"query": query, "endpoint": "symbols/search"},
        data={"results": []},
        meta=ResponseMeta(warnings=[]),
    ).model_dump(mode="json")


@router.get("/{symbol}/metadata")
async def get_symbol_metadata(symbol: str):
    """
    Get metadata for a specific symbol.

    TODO: Implement provider-backed metadata lookup.
    """
    symbol = validate_symbol(symbol)
    return ResponseEnvelope(
        request={"symbol": symbol, "endpoint": "symbols/metadata"},
        data={"symbol": symbol},
        meta=ResponseMeta(warnings=[]),
    ).model_dump(mode="json")
