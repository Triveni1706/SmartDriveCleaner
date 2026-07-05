"""
Background job tracking for the two-stage scan architecture.

Quick scans and deep-analysis runs both execute on a background thread so
the HTTP request returns instantly with a job id. The frontend polls
GET /api/jobs/{id} for current_task / percent / eta while the work happens.

Jobs are persisted to the scan_jobs table (not just kept in memory) so a
page refresh mid-scan can still recover progress.
"""
import json
import threading
import time
import uuid
from datetime import datetime
from typing import Callable

from database.db import SessionLocal
from database.models import ScanJob

_lock = threading.Lock()
# job_id -> perf_counter() at start, used for ETA math without re-parsing datetimes
_start_clock: dict[str, float] = {}


def create_job(job_type: str, root_path: str | None = None, categories: list[str] | None = None) -> str:
    job_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        job = ScanJob(
            id=job_id,
            job_type=job_type,
            status="pending",
            root_path=root_path,
            categories=",".join(categories) if categories else None,
            total_items=0,
            completed_items=0,
            current_task="Queued",
            percent=0.0,
            started_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
    finally:
        db.close()
    _start_clock[job_id] = time.perf_counter()
    return job_id


def update_job(job_id: str, **fields):
    """Thread-safe partial update. Called frequently (every N files) from
    worker threads, so keep it cheap — one UPDATE statement."""
    with _lock:
        db = SessionLocal()
        try:
            job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
            if not job:
                return
            for key, value in fields.items():
                setattr(job, key, value)
            db.commit()
        finally:
            db.close()


def finish_job(job_id: str, status: str = "completed", result: dict | None = None, error: str | None = None):
    update_job(
        job_id,
        status=status,
        percent=100.0 if status == "completed" else None,
        current_task="Done" if status == "completed" else "Failed",
        finished_at=datetime.utcnow(),
        result_json=json.dumps(result) if result is not None else None,
        error=error,
    )
    _start_clock.pop(job_id, None)


def eta_seconds(job_id: str, completed: int, total: int) -> float | None:
    if total <= 0 or completed <= 0:
        return None
    started = _start_clock.get(job_id)
    if started is None:
        return None
    elapsed = time.perf_counter() - started
    rate = completed / elapsed if elapsed > 0 else 0
    if rate <= 0:
        return None
    remaining = max(total - completed, 0)
    return round(remaining / rate, 1)


def get_job(job_id: str) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        if not job:
            return None
        eta = eta_seconds(job_id, job.completed_items or 0, job.total_items or 0) if job.status == "running" else None
        return {
            "id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "root_path": job.root_path,
            "categories": job.categories.split(",") if job.categories else [],
            "total_items": job.total_items or 0,
            "completed_items": job.completed_items or 0,
            "current_task": job.current_task,
            "percent": job.percent,
            "eta_seconds": eta,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "error": job.error,
            "result": json.loads(job.result_json) if job.result_json else None,
        }
    finally:
        db.close()


def run_in_background(target: Callable, *args, **kwargs):
    thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    return thread
