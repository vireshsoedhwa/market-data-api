"""V2 refresh and job-status endpoints with response envelope."""

import uuid

from fastapi import APIRouter, Depends

from app.dependencies import verify_api_key
from app.schemas.v2 import ResponseEnvelope, ResponseMeta
from app.validation import validate_batch_symbols

router = APIRouter(prefix="/v2", tags=["refresh"], dependencies=[Depends(verify_api_key)])


@router.post("/refresh")
async def request_refresh(request: dict):
    """
    Queue a data refresh for the given symbols.

    TODO: Dispatch Celery tasks to market-data-worker.
    """
    raw_symbols = request.get("symbols", [])
    symbols = validate_batch_symbols(raw_symbols)

    job_id = f"refresh_{uuid.uuid4().hex[:12]}"
    data = {
        "job_id": job_id,
        "status": "queued",
        "symbols_queued": symbols,
    }

    return ResponseEnvelope(
        request={"symbols": symbols, "endpoint": "refresh"},
        data=data,
        meta=ResponseMeta(warnings=[]),
    ).model_dump(mode="json")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Check the status of a refresh job.

    TODO: Look up job in market_data.market_data_fetch_jobs.
    """
    data = {
        "job_id": job_id,
        "status": "unknown",
    }

    return ResponseEnvelope(
        request={"job_id": job_id, "endpoint": "jobs"},
        data=data,
        meta=ResponseMeta(warnings=[]),
    ).model_dump(mode="json")
