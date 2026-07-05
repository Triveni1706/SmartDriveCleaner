from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.db import get_db
from database.models import OrganizeBatch, ScannedFile
from models.schemas import (
    OrganizeMode, OrganizePreview, PlannedMove, OrganizeRunResult,
    UndoRequest, UndoResult, OrganizeBatchOut, OrganizeStats,
    DuplicateScanRequest, DuplicateGroupOut, DuplicateDeleteRequest, DuplicateDeleteResult,
    EmptyFolderScanRequest,
)
from models.schemas import EmptyFolder
from services import organizer

router = APIRouter()


def _plan_for_mode(mode: str, root: str, include_hidden: bool) -> dict:
    if mode == "category":
        return organizer.plan_category_organize(root, include_hidden)
    if mode == "merge_by_type":
        return organizer.plan_merge_by_type(root, include_hidden)
    if mode == "separate_files_folders":
        return organizer.plan_separate_files_folders(root, include_hidden)
    raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")


def _execute_for_mode(db: Session, mode: str, root: str, include_hidden: bool) -> dict:
    if mode == "category":
        return organizer.execute_category_organize(db, root, include_hidden)
    if mode == "merge_by_type":
        return organizer.execute_merge_by_type(db, root, include_hidden)
    if mode == "separate_files_folders":
        return organizer.execute_separate_files_folders(db, root, include_hidden)
    raise HTTPException(status_code=400, detail=f"Unknown mode: {mode}")


@router.post("/preview-organize", response_model=OrganizePreview)
def preview_organize(request: OrganizeMode):
    try:
        plan = _plan_for_mode(request.mode, request.root, request.include_hidden)
    except organizer.OrganizerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return OrganizePreview(
        root=plan["root"],
        mode=request.mode,
        moves=[PlannedMove(**m) for m in plan["moves"]],
        folders_to_create=plan["folders_to_create"],
        total_files=len(plan["moves"]),
    )


@router.post("/organize", response_model=OrganizeRunResult)
def organize(request: OrganizeMode, db: Session = Depends(get_db)):
    """Executes the move plan for real: creates category folders and calls
    shutil.move() on every matched file. Changes are visible in Explorer
    immediately since nothing here uses a virtual/staged filesystem."""
    try:
        result = _execute_for_mode(db, request.mode, request.root, request.include_hidden)
    except organizer.OrganizerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return OrganizeRunResult(**result)


@router.post("/undo-organize", response_model=UndoResult)
def undo_organize(request: UndoRequest, db: Session = Depends(get_db)):
    batch_id = request.batch_id
    if not batch_id:
        latest = organizer.latest_undoable_batch(db)
        if not latest:
            raise HTTPException(status_code=404, detail="No organization run available to undo")
        batch_id = latest.id
    try:
        result = organizer.undo_batch(db, batch_id)
    except organizer.OrganizerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return UndoResult(**result)


@router.get("/organization-history", response_model=list[OrganizeBatchOut])
def organization_history(limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(OrganizeBatch)
        .order_by(OrganizeBatch.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/organization-stats", response_model=OrganizeStats)
def organization_stats(db: Session = Depends(get_db)):
    stats = organizer.get_stats(db)
    total_indexed = db.query(func.count(ScannedFile.id)).scalar() or 0
    return OrganizeStats(**stats, total_files_indexed=total_indexed)


# --- Duplicate cleanup (preview -> confirm) ---

@router.post("/organize/duplicates/scan", response_model=list[DuplicateGroupOut])
def scan_duplicates(request: DuplicateScanRequest):
    try:
        groups = organizer.find_duplicates(request.root, request.include_hidden)
    except organizer.OrganizerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [DuplicateGroupOut(**g) for g in groups]


@router.post("/organize/duplicates/delete", response_model=DuplicateDeleteResult)
def delete_duplicates(request: DuplicateDeleteRequest, db: Session = Depends(get_db)):
    """Deletes only the exact paths the user confirmed after reviewing the
    preview — never a whole group automatically."""
    result = organizer.delete_confirmed_duplicates(db, request.file_paths)
    return DuplicateDeleteResult(**result)


# --- Empty folder cleanup ---

@router.post("/organize/empty-folders/scan", response_model=list[EmptyFolder])
def scan_empty_folders(request: EmptyFolderScanRequest):
    return [EmptyFolder(**d) for d in organizer.find_empty_folders(request.root)]


@router.delete("/organize/empty-folders")
def clean_empty_folders(request: dict):
    paths = request.get("paths", [])
    return organizer.delete_empty_folders(paths)
