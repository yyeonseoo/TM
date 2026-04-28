from fastapi import APIRouter, HTTPException

from backend.storage.schemas import JobStatusResponse
from backend.services.job_service import get_job


router = APIRouter(tags=["jobs"])


@router.get("/jobs/{jobId}", response_model=JobStatusResponse)
def get_job_status(jobId: str):
    job = get_job(jobId)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusResponse(**job)

