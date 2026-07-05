from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import ScannedFile, AuditLog
from models.schemas import (
    QuickScanRequest, JobHandle, JobStatus, CategoryStatsResponse, CategoryStat,
    DeepScanRequest,
)
from services import job_manager
from services.quick_scan import run_quick_scan
from services.deep_analysis import run_deep_scan, estimate_seconds, EXTRA_ANALYSIS

router = APIRouter()

# Categories that make sense to offer for deep analysis in the dashboard.
# "Others" (unmatched extensions) has nothing meaningful to analyze beyond
# what quick scan already captured.
ANALYZABLE_CATEGORIES = {"Images", "PDFs", "Archives", "Documents", "Videos", "Audio"}


@router.post("/quick-scan", response_model=JobHandle)
def quick_scan(request: QuickScanRequest, db: Session = Depends(get_db)):
    job_id = job_manager.create_job("quick_scan", root_path=request.path)
    db.add(AuditLog(action="quick_scan_started", detail=f"{request.path} (job {job_id})"))
    db.commit()
    job_manager.run_in_background(run_quick_scan, job_id, request.path)
    return JobHandle(job_id=job_id)


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/category-stats", response_model=CategoryStatsResponse)
def category_stats(db: Session = Depends(get_db)):
    """Stage 1 output: per-category counts/sizes/time estimates, computed
    purely from the metadata quick scan already collected — no file content
    is touched here."""
    rows = (
        db.query(ScannedFile.category, func.count(ScannedFile.id), func.sum(ScannedFile.size_bytes))
        .group_by(ScannedFile.category)
        .all()
    )
    total_files = sum(r[1] for r in rows)
    total_bytes = sum(r[2] or 0 for r in rows)

    most_recent_root = db.query(ScannedFile.scan_root).order_by(ScannedFile.id.desc()).first()

    categories = [
        CategoryStat(
            category=category,
            file_count=count,
            total_bytes=size or 0,
            estimated_seconds=estimate_seconds(category, count),
            supports_deep_analysis=category in ANALYZABLE_CATEGORIES,
        )
        for category, count, size in rows
    ]
    categories.sort(key=lambda c: c.total_bytes, reverse=True)

    return CategoryStatsResponse(
        root_path=most_recent_root[0] if most_recent_root else None,
        total_files=total_files,
        total_bytes=total_bytes,
        categories=categories,
    )


@router.post("/deep-scan", response_model=JobHandle)
def deep_scan(request: DeepScanRequest, db: Session = Depends(get_db)):
    categories = [c for c in request.categories if c in ANALYZABLE_CATEGORIES]
    if not categories:
        raise HTTPException(status_code=400, detail="No valid categories selected")

    job_id = job_manager.create_job("deep_scan", categories=categories)
    db.add(AuditLog(action="deep_scan_started", detail=f"{', '.join(categories)} (job {job_id})"))
    db.commit()
    job_manager.run_in_background(run_deep_scan, job_id, categories)
    return JobHandle(job_id=job_id)
