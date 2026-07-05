from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db
from api.files import router as files_router
from api.phase3 import router as phase3_router
from api.scan import router as scan_router
from api.file_ops import router as file_ops_router
from api.collections import router as collections_router
from api.organize import router as organize_router
from services.monitor import monitor
from services import scheduler as scheduler_service

app = FastAPI(title="Smart Drive Cleaner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(phase3_router, prefix="/api", tags=["phase3"])
app.include_router(scan_router, prefix="/api", tags=["scan"])
app.include_router(file_ops_router, prefix="/api", tags=["file-ops"])
app.include_router(collections_router, prefix="/api", tags=["collections"])
app.include_router(organize_router, prefix="/api", tags=["organize"])


@app.on_event("shutdown")
def _on_shutdown():
    monitor.stop()
    scheduler_service.shutdown()


@app.get("/")
def root():
    return {"status": "ok", "service": "Smart Drive Cleaner API"}
