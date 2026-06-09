from fastapi import APIRouter, Depends, Query

from app.dependencies import verify_api_key
from app.schemas.common import SymbolMetadataResponse, SymbolSearchResponse

router = APIRouter(prefix="/v1/symbols", tags=["symbols"], dependencies=[Depends(verify_api_key)])


@router.get("/search", response_model=SymbolSearchResponse)
async def search_symbols(query: str = Query(..., min_length=1)):
    """
    Search for symbols matching the query string.

    TODO: Implement provider-backed symbol search.
    """
    return SymbolSearchResponse(results=[])


@router.get("/{symbol}/metadata", response_model=SymbolMetadataResponse)
async def get_symbol_metadata(symbol: str):
    """
    Get metadata for a specific symbol.

    TODO: Implement provider-backed metadata lookup.
    """
    return SymbolMetadataResponse(symbol=symbol.upper())
