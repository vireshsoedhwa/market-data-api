"""V2 providers endpoint with response envelope."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import verify_api_key
from app.schemas.v2 import ResponseEnvelope, ResponseMeta

router = APIRouter(prefix="/v2/providers", tags=["providers"], dependencies=[Depends(verify_api_key)])


@router.get("/status")
async def get_providers_status(db: AsyncSession = Depends(get_db)):
    """Return the current status of all registered providers."""
    query = text("""
        SELECT
            p.name,
            p.display_name,
            p.is_enabled,
            p.supports_latest_price,
            p.supports_daily_history,
            COALESCE(h.status, 'unknown') AS health_status
        FROM market_data.market_data_providers p
        LEFT JOIN market_data.provider_health_state h ON h.provider_id = p.id
        ORDER BY p.name
    """)

    result = await db.execute(query)
    rows = result.fetchall()

    providers = [
        {
            "name": row.name,
            "display_name": row.display_name,
            "is_enabled": row.is_enabled,
            "status": row.health_status,
            "supports_latest_price": row.supports_latest_price,
            "supports_daily_history": row.supports_daily_history,
        }
        for row in rows
    ]

    return ResponseEnvelope(
        request={"endpoint": "providers/status"},
        data={"providers": providers},
        meta=ResponseMeta(
            as_of=datetime.now(timezone.utc),
            warnings=[],
        ),
    ).model_dump(mode="json")
