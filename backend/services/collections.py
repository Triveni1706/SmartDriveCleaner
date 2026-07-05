"""Custom Collection Manager — user-defined groupings of files
(e.g. "Important PDFs", "Certificates", "Resumes")."""
from sqlalchemy.orm import Session
from database.models import Collection, CollectionFile, ScannedFile, AuditLog


class CollectionError(Exception):
    pass


def create_collection(db: Session, name: str) -> Collection:
    name = name.strip()
    if not name:
        raise CollectionError("Collection name cannot be empty")
    if db.query(Collection).filter(Collection.name == name).first():
        raise CollectionError(f"A collection named '{name}' already exists")
    c = Collection(name=name)
    db.add(c)
    db.add(AuditLog(action="collection_created", detail=name))
    db.commit()
    db.refresh(c)
    return c


def rename_collection(db: Session, collection_id: int, new_name: str) -> Collection:
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise CollectionError("Collection not found")
    new_name = new_name.strip()
    if not new_name:
        raise CollectionError("Collection name cannot be empty")
    if db.query(Collection).filter(Collection.name == new_name, Collection.id != collection_id).first():
        raise CollectionError(f"A collection named '{new_name}' already exists")
    c.name = new_name
    db.commit()
    db.refresh(c)
    return c


def delete_collection(db: Session, collection_id: int):
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise CollectionError("Collection not found")
    db.query(CollectionFile).filter(CollectionFile.collection_id == collection_id).delete()
    db.delete(c)
    db.add(AuditLog(action="collection_deleted", detail=c.name))
    db.commit()


def list_collections(db: Session) -> list[dict]:
    collections = db.query(Collection).order_by(Collection.name).all()
    out = []
    for c in collections:
        count = db.query(CollectionFile).filter(CollectionFile.collection_id == c.id).count()
        bytes_total = 0
        file_ids = [cf.file_id for cf in db.query(CollectionFile).filter(CollectionFile.collection_id == c.id).all()]
        if file_ids:
            files = db.query(ScannedFile).filter(ScannedFile.id.in_(file_ids)).all()
            bytes_total = sum(f.size_bytes or 0 for f in files)
        out.append({"id": c.id, "name": c.name, "created_at": c.created_at, "file_count": count, "total_bytes": bytes_total})
    return out


def add_files(db: Session, collection_id: int, file_ids: list[int]) -> int:
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise CollectionError("Collection not found")
    existing = {
        cf.file_id
        for cf in db.query(CollectionFile).filter(
            CollectionFile.collection_id == collection_id, CollectionFile.file_id.in_(file_ids)
        ).all()
    }
    added = 0
    for fid in file_ids:
        if fid in existing:
            continue
        db.add(CollectionFile(collection_id=collection_id, file_id=fid))
        added += 1
    db.commit()
    return added


def remove_files(db: Session, collection_id: int, file_ids: list[int]) -> int:
    q = db.query(CollectionFile).filter(
        CollectionFile.collection_id == collection_id, CollectionFile.file_id.in_(file_ids)
    )
    removed = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    return removed


def get_collection_files(db: Session, collection_id: int) -> list[ScannedFile]:
    file_ids = [cf.file_id for cf in db.query(CollectionFile).filter(CollectionFile.collection_id == collection_id).all()]
    if not file_ids:
        return []
    return db.query(ScannedFile).filter(ScannedFile.id.in_(file_ids)).order_by(ScannedFile.size_bytes.desc()).all()
