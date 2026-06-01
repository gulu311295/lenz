import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Job, JobStatus
from .schemas import JobCreatedResponse, JobResultResponse, JobStatusResponse
from .worker import shutdown_worker, submit_job


MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/uploads"))

app = FastAPI(title="Consumer Sentiment AI App")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("shutdown")
def on_shutdown() -> None:
    shutdown_worker()


@app.post("/jobs", response_model=JobCreatedResponse)
@app.post("/api/jobs", response_model=JobCreatedResponse, include_in_schema=False)
async def create_job(file: UploadFile = File(...), db: Session = Depends(get_db)) -> JobCreatedResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 2 MB.")

    job = Job(filename=file.filename, file_path="")
    db.add(job)
    db.flush()

    destination = UPLOAD_DIR / f"{job.id}.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as out_file:
        out_file.write(content)

    job.file_path = str(destination.resolve())
    job.status = JobStatus.queued
    db.commit()

    submit_job(job.id)
    return JobCreatedResponse(job_id=job.id, status=job.status.value)


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse, include_in_schema=False)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@app.get("/jobs/{job_id}/result", response_model=JobResultResponse)
@app.get("/api/jobs/{job_id}/result", response_model=JobResultResponse, include_in_schema=False)
def get_job_result(job_id: str, db: Session = Depends(get_db)) -> JobResultResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != JobStatus.completed:
        raise HTTPException(status_code=400, detail=f"Job is {job.status.value}.")
    if not job.result:
        raise HTTPException(status_code=500, detail="Result missing for completed job.")

    payload = json.loads(job.result.summary_json)
    return JobResultResponse(job_id=job.id, status=job.status.value, result=payload)
