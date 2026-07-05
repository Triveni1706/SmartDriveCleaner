from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import ScannedFile, TrashItem
from models.schemas import (
    OpenRequest, RenameRequest, MoveRequest, CopyRequest, FileOpResult,
    TrashRequest, TrashItemOut, TrashActionResult, EmptyFolder, ZipBackupPair,
    SearchIndexStatus,
)
from services import file_ops
from services.archive_analyzer import detect_zip_backups

router = APIRouter()


# --- Open / open containing folder ---

@router.post("/file-ops/open")
def open_file(request: OpenRequest, db: Session = Depends(get_db)):
    f = db.query(ScannedFile).filter(ScannedFile.id == request.file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        file_ops.open_file(f.path)
    except file_ops.FileOpError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"opened": f.path}


@router.post("/file-ops/open-folder")
def open_folder(request: OpenRequest, db: Session = Depends(get_db)):
    f = db.query(ScannedFile).filter(ScannedFile.id == request.file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        file_ops.open_containing_folder(f.path)
    except file_ops.FileOpError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"opened_folder_for": f.path}


# --- Rename / Move / Copy ---

@router.post("/file-ops/rename", response_model=FileOpResult)
def rename(request: RenameRequest, db: Session = Depends(get_db)):
    try:
        f = file_ops.rename_file(db, request.file_id, request.new_name)
        return FileOpResult(ok=True, file=f)
    except file_ops.FileOpError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/file-ops/move", response_model=FileOpResult)
def move(request: MoveRequest, db: Session = Depends(get_db)):
    try:
        f = file_ops.move_file(db, request.file_id, request.destination_folder)
        return FileOpResult(ok=True, file=f)
    except file_ops.FileOpError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/file-ops/copy", response_model=FileOpResult)
def copy(request: CopyRequest, db: Session = Depends(get_db)):
    try:
        f = file_ops.copy_file(db, request.file_id, request.destination_folder)
        return FileOpResult(ok=True, file=f)
    except file_ops.FileOpError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Safe delete / trash / recovery center ---

@router.post("/files/trash", response_model=TrashActionResult)
def trash_files(request: TrashRequest, db: Session = Depends(get_db)):
    """Safe delete: moves files into SmartDriveCleaner_Trash instead of
    removing them from disk. Use /api/files (DELETE) for a hard, permanent
    delete instead (kept for backward compatibility)."""
    result = file_ops.soft_delete_files(db, request.file_ids)
    return TrashActionResult(deleted=result["deleted"], failed=result["failed"])


@router.get("/trash", response_model=list[TrashItemOut])
def get_trash(db: Session = Depends(get_db)):
    return file_ops.list_trash(db)


@router.post("/trash/restore", response_model=TrashActionResult)
def restore_trash(request: TrashRequest, db: Session = Depends(get_db)):
    result = file_ops.restore_files(db, request.file_ids)
    return TrashActionResult(restored=result["restored"], failed=result["failed"])


@router.delete("/trash/permanent", response_model=TrashActionResult)
def purge_trash(request: TrashRequest, db: Session = Depends(get_db)):
    result = file_ops.purge_trash(db, request.file_ids)
    return TrashActionResult(purged=result["purged"], failed=result["failed"])


@router.delete("/trash/empty", response_model=TrashActionResult)
def empty_trash(db: Session = Depends(get_db)):
    result = file_ops.purge_trash(db, None)
    return TrashActionResult(purged=result["purged"], failed=result["failed"])


# --- Empty folders ---

@router.get("/empty-folders", response_model=list[EmptyFolder])
def empty_folders(db: Session = Depends(get_db)):
    most_recent_root = db.query(ScannedFile.scan_root).order_by(ScannedFile.id.desc()).first()
    root = most_recent_root[0] if most_recent_root else None
    if not root:
        return []
    return [EmptyFolder(**d) for d in file_ops.find_empty_folders(root)]


@router.delete("/empty-folders")
def delete_empty_folders(request: dict, db: Session = Depends(get_db)):
    paths = request.get("paths", [])
    return file_ops.delete_empty_folders(paths)


# --- ZIP backup detection ---

@router.get("/zip-backups", response_model=list[ZipBackupPair])
def zip_backups(db: Session = Depends(get_db)):
    archives = db.query(ScannedFile).filter(ScannedFile.category == "Archives").all()
    return [ZipBackupPair(**p) for p in detect_zip_backups(archives)]


# --- Search index status (persistent search dashboard strip) ---

@router.get("/search/status", response_model=SearchIndexStatus)
def search_status(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from database.models import ScanJob

    indexed_files = db.query(func.count(ScannedFile.id)).scalar() or 0
    last_job = (
        db.query(ScanJob)
        .filter(ScanJob.status == "completed")
        .order_by(ScanJob.finished_at.desc())
        .first()
    )
    if indexed_files == 0:
        status = "empty"
    else:
        status = "ready"
    return SearchIndexStatus(
        indexed_files=indexed_files,
        last_scan=last_job.finished_at if last_job else None,
        status=status,
    )
