"""
Cleanup scheduler: runs recurring jobs (daily/weekly/monthly) that generate
a fresh PDF report and, optionally, auto-clean safe categories (exact
duplicates only — never blurry/old files without explicit confirmation,
since those are judgment calls, not certainties).

Uses APScheduler's BackgroundScheduler, which runs jobs in-process on a
background thread — no external cron/task-scheduler setup needed.
"""
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database.db import SessionLocal
from database.models import ScannedFile, AuditLog, ScheduledRun
from services.report_generator import generate_pdf_report

FREQUENCIES = {
    "daily": CronTrigger(hour=3, minute=0),        # 3 AM daily
    "weekly": CronTrigger(day_of_week="sun", hour=3, minute=0),
    "monthly": CronTrigger(day=1, hour=3, minute=0),
}

_scheduler = BackgroundScheduler()
_active_jobs: dict[str, dict] = {}  # job_name -> {frequency, auto_clean_duplicates}


def _run_cleanup_job(job_name: str, frequency: str, auto_clean_duplicates: bool):
    db = SessionLocal()
    try:
        files_affected, bytes_recovered = 0, 0

        if auto_clean_duplicates:
            # Only ever touches exact SHA256 duplicates, never the original,
            # never blurry/near-duplicate/old-file categories — those need a
            # human decision, exact duplicates by definition don't lose data.
            dups = db.query(ScannedFile).filter(ScannedFile.is_duplicate == True).all()
            import os as _os
            for f in dups:
                try:
                    if _os.path.exists(f.path):
                        _os.remove(f.path)
                    files_affected += 1
                    bytes_recovered += f.size_bytes or 0
                    db.delete(f)
                except OSError:
                    continue
            db.commit()

        report_path = generate_pdf_report(db)

        db.add(ScheduledRun(
            job_name=job_name,
            frequency=frequency,
            files_affected=files_affected,
            bytes_recovered=bytes_recovered,
            detail=f"Report: {report_path}",
        ))
        db.add(AuditLog(
            action="scheduled_cleanup",
            detail=f"{job_name} ({frequency}): {files_affected} files, {bytes_recovered} bytes freed",
        ))
        db.commit()
    finally:
        db.close()


def schedule_job(job_name: str, frequency: str, auto_clean_duplicates: bool = False):
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {list(FREQUENCIES)}")

    if job_name in _active_jobs:
        _scheduler.remove_job(job_name)

    _scheduler.add_job(
        _run_cleanup_job,
        trigger=FREQUENCIES[frequency],
        args=[job_name, frequency, auto_clean_duplicates],
        id=job_name,
        replace_existing=True,
    )
    _active_jobs[job_name] = {"frequency": frequency, "auto_clean_duplicates": auto_clean_duplicates}

    if not _scheduler.running:
        _scheduler.start()


def unschedule_job(job_name: str):
    if job_name in _active_jobs:
        _scheduler.remove_job(job_name)
        del _active_jobs[job_name]


def list_jobs() -> list[dict]:
    return [{"job_name": name, **cfg} for name, cfg in _active_jobs.items()]


def run_job_now(job_name: str):
    """Manual trigger — e.g. a 'Run now' button, doesn't wait for the cron."""
    cfg = _active_jobs.get(job_name)
    if not cfg:
        raise ValueError(f"No such scheduled job: {job_name}")
    _run_cleanup_job(job_name, cfg["frequency"], cfg["auto_clean_duplicates"])


def shutdown():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
