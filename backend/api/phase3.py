import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import AuditLog, ScheduledRun
from models.schemas import (
    MonitorStartRequest, MonitorStatus, SearchRequest, SearchResponse,
    ChatRequest, ChatResponse, ScheduleJobRequest, ScheduledJobOut,
    AuditLogOut, ScheduledRunOut,
)
from services.monitor import monitor
from services.smart_search import run_search
from services.chat_assistant import answer as chat_answer
from services import scheduler as scheduler_service
from services.report_generator import generate_pdf_report
from database.models import AuditLog as AuditLogModel

router = APIRouter()


# --- Real-time monitoring ---

@router.post("/monitor/start", response_model=MonitorStatus)
def start_monitor(request: MonitorStartRequest):
    try:
        monitor.start(request.path, auto_organize=request.auto_organize)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return monitor.status()


@router.post("/monitor/stop", response_model=MonitorStatus)
def stop_monitor():
    monitor.stop()
    return monitor.status()


@router.get("/monitor/status", response_model=MonitorStatus)
def monitor_status():
    return monitor.status()


# --- Smart search ---

@router.post("/search", response_model=SearchResponse)
def smart_search(request: SearchRequest, db: Session = Depends(get_db)):
    return run_search(db, request.query)


# --- AI chat assistant ---

@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    return chat_answer(db, request.message)


# --- Scheduler ---

@router.post("/scheduler/jobs", response_model=ScheduledJobOut)
def create_job(request: ScheduleJobRequest, db: Session = Depends(get_db)):
    try:
        scheduler_service.schedule_job(request.job_name, request.frequency, request.auto_clean_duplicates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.add(AuditLogModel(action="job_scheduled", detail=f"{request.job_name} ({request.frequency})"))
    db.commit()
    return {"job_name": request.job_name, "frequency": request.frequency, "auto_clean_duplicates": request.auto_clean_duplicates}


@router.get("/scheduler/jobs", response_model=list[ScheduledJobOut])
def list_jobs():
    return scheduler_service.list_jobs()


@router.delete("/scheduler/jobs/{job_name}")
def delete_job(job_name: str):
    scheduler_service.unschedule_job(job_name)
    return {"deleted": job_name}


@router.post("/scheduler/jobs/{job_name}/run")
def run_job(job_name: str):
    try:
        scheduler_service.run_job_now(job_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ran": job_name}


@router.get("/scheduler/runs", response_model=list[ScheduledRunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(ScheduledRun).order_by(ScheduledRun.ran_at.desc()).limit(50).all()


# --- Reports ---

@router.post("/reports/generate")
def generate_report(db: Session = Depends(get_db)):
    filepath = generate_pdf_report(db)
    db.add(AuditLogModel(action="report_generated", detail=filepath))
    db.commit()
    return {"filepath": filepath, "filename": os.path.basename(filepath)}


@router.get("/reports/{filename}")
def download_report(filename: str):
    from services.report_generator import REPORTS_DIR
    filepath = os.path.join(REPORTS_DIR, filename)
    if not os.path.isfile(filepath) or not filename.endswith(".pdf"):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)


# --- Audit log ---

@router.get("/audit-log", response_model=list[AuditLogOut])
def audit_log(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
