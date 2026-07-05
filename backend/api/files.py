import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.db import get_db
from database.models import ScannedFile, AuditLog
from models.schemas import ScanRequest, ScanResult, FileOut, StorageStats, DeleteRequest, Recommendation
from services.scanner import scan_directory
from services.recommendations import generate_recommendations

router = APIRouter()


@router.post("/scan", response_model=ScanResult)
def scan(request: ScanRequest, db: Session = Depends(get_db)):
    try:
        result = scan_directory(request.path, db)
        db.add(AuditLog(action="scan", detail=f"{request.path}: {result['scanned_files']} files"))
        db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/files", response_model=list[FileOut])
def list_files(category: str | None = None, skip: int = 0, limit: int = 200, db: Session = Depends(get_db)):
    query = db.query(ScannedFile)
    if category:
        query = query.filter(ScannedFile.category == category)
    return query.order_by(ScannedFile.modified_at.asc()).offset(skip).limit(limit).all()


@router.get("/duplicates", response_model=list[FileOut])
def list_duplicates(db: Session = Depends(get_db)):
    return (
        db.query(ScannedFile)
        .filter(ScannedFile.duplicate_group.isnot(None))
        .order_by(ScannedFile.duplicate_group, ScannedFile.is_duplicate.desc())
        .all()
    )


@router.get("/similar-images", response_model=list[FileOut])
def list_similar_images(db: Session = Depends(get_db)):
    return (
        db.query(ScannedFile)
        .filter(ScannedFile.similar_group.isnot(None))
        .order_by(ScannedFile.similar_group)
        .all()
    )


@router.get("/blurry-images", response_model=list[FileOut])
def list_blurry_images(db: Session = Depends(get_db)):
    return (
        db.query(ScannedFile)
        .filter(ScannedFile.is_blurry == True)
        .order_by(ScannedFile.blur_score.asc())
        .all()
    )


@router.get("/pdfs", response_model=list[FileOut])
def list_pdfs(subcategory: str | None = None, db: Session = Depends(get_db)):
    query = db.query(ScannedFile).filter(ScannedFile.category == "PDFs")
    if subcategory:
        query = query.filter(ScannedFile.subcategory == subcategory)
    return query.order_by(ScannedFile.subcategory_confidence.desc()).all()


@router.get("/archives", response_model=list[FileOut])
def list_archives(db: Session = Depends(get_db)):
    return (
        db.query(ScannedFile)
        .filter(ScannedFile.category == "Archives")
        .order_by(ScannedFile.size_bytes.desc())
        .all()
    )


@router.get("/recommendations", response_model=list[Recommendation])
def recommendations(categories: str | None = None, db: Session = Depends(get_db)):
    cats = categories.split(",") if categories else None
    return generate_recommendations(db, cats)


@router.get("/stats", response_model=StorageStats)
def stats(db: Session = Depends(get_db)):
    total_files = db.query(func.count(ScannedFile.id)).scalar() or 0
    total_bytes = db.query(func.sum(ScannedFile.size_bytes)).scalar() or 0

    by_category = {}
    rows = (
        db.query(ScannedFile.category, func.count(ScannedFile.id), func.sum(ScannedFile.size_bytes))
        .group_by(ScannedFile.category)
        .all()
    )
    for category, count, size in rows:
        by_category[category] = {"count": count, "bytes": size or 0}

    duplicate_files = db.query(func.count(ScannedFile.id)).filter(ScannedFile.is_duplicate == True).scalar() or 0
    duplicate_wasted_bytes = (
        db.query(func.sum(ScannedFile.size_bytes)).filter(ScannedFile.is_duplicate == True).scalar() or 0
    )

    return StorageStats(
        total_files=total_files,
        total_bytes=total_bytes,
        by_category=by_category,
        duplicate_files=duplicate_files,
        duplicate_wasted_bytes=duplicate_wasted_bytes,
    )


@router.delete("/files")
def delete_files(request: DeleteRequest, db: Session = Depends(get_db)):
    deleted, failed = [], []
    files = db.query(ScannedFile).filter(ScannedFile.id.in_(request.file_ids)).all()
    for f in files:
        try:
            if os.path.exists(f.path):
                os.remove(f.path)
            db.delete(f)
            deleted.append(f.id)
        except OSError as e:
            failed.append({"id": f.id, "error": str(e)})
    if deleted:
        db.add(AuditLog(action="files_deleted", detail=f"{len(deleted)} files deleted manually"))
    db.commit()
    return {"deleted": deleted, "failed": failed}
