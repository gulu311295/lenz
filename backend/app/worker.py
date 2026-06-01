import json
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from .database import SessionLocal
from .llm import analyze_feedback
from .models import Job, JobResult, JobStatus
from .parser import extract_feedback_from_pdf


_executor = ThreadPoolExecutor(max_workers=3)


def process_job(job_id: str) -> None:
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return

        job.status = JobStatus.running
        job.error_message = None
        db.commit()

        with open(job.file_path, "rb") as f:
            content = f.read()

        entries = extract_feedback_from_pdf(content)
        payload = [{"feedback_id": e.feedback_id, "comment": e.comment} for e in entries]
        result = analyze_feedback(payload)

        existing_result = db.get(JobResult, job_id)
        if existing_result:
            existing_result.summary_json = json.dumps(result)
        else:
            db.add(JobResult(job_id=job_id, summary_json=json.dumps(result)))

        job.status = JobStatus.completed
        db.commit()
    except Exception as exc:  # noqa: BLE001
        failed_job = db.get(Job, job_id)
        if failed_job:
            failed_job.status = JobStatus.failed
            failed_job.error_message = str(exc)
            db.commit()
    finally:
        db.close()


def submit_job(job_id: str) -> None:
    _executor.submit(process_job, job_id)


def shutdown_worker() -> None:
    _executor.shutdown(wait=False, cancel_futures=False)
