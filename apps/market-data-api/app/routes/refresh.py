import uuid

from fastapi import APIRouter, Depends

from app.dependencies import verify_api_key
from app.schemas.common import JobStatusResponse, RefreshRequest, RefreshResponse

router = APIRouter(prefix="/v1", tags=["refresh"], dependencies=[Depends(verify_api_key)])


@router.post("/refresh", response_model=RefreshResponse)
async def request_refresh(request: RefreshRequest):
    """
    Queue a data refresh for the given symbols.

    TODO: Dispatch Celery tasks to market-data-worker.
    """
    job_id = f"refresh_{uuid.uuid4().hex[:12]}"
    return RefreshResponse(
        job_id=job_id,
        status="queued",
        symbols_queued=request.symbols,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Check the status of a refresh job.

    TODO: Look up job in market_data.market_data_fetch_jobs.
    """
    return JobStatusResponse(
        job_id=job_id,
        status="unknown",
    )
