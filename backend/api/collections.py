from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.db import get_db
from models.schemas import (
    CollectionCreateRequest, CollectionRenameRequest, CollectionFilesRequest,
    CollectionOut, FileOut,
)
from services import collections as collections_service

router = APIRouter()


@router.post("/collections", response_model=CollectionOut)
def create_collection(request: CollectionCreateRequest, db: Session = Depends(get_db)):
    try:
        c = collections_service.create_collection(db, request.name)
    except collections_service.CollectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CollectionOut(id=c.id, name=c.name, created_at=c.created_at, file_count=0, total_bytes=0)


@router.get("/collections", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    return collections_service.list_collections(db)


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
def rename_collection(collection_id: int, request: CollectionRenameRequest, db: Session = Depends(get_db)):
    try:
        c = collections_service.rename_collection(db, collection_id, request.name)
    except collections_service.CollectionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    files = collections_service.get_collection_files(db, collection_id)
    return CollectionOut(
        id=c.id, name=c.name, created_at=c.created_at,
        file_count=len(files), total_bytes=sum(f.size_bytes or 0 for f in files),
    )


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    try:
        collections_service.delete_collection(db, collection_id)
    except collections_service.CollectionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"deleted": collection_id}


@router.post("/collections/{collection_id}/files")
def add_files(collection_id: int, request: CollectionFilesRequest, db: Session = Depends(get_db)):
    try:
        added = collections_service.add_files(db, collection_id, request.file_ids)
    except collections_service.CollectionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"added": added}


@router.delete("/collections/{collection_id}/files")
def remove_files(collection_id: int, request: CollectionFilesRequest, db: Session = Depends(get_db)):
    removed = collections_service.remove_files(db, collection_id, request.file_ids)
    return {"removed": removed}


@router.get("/collections/{collection_id}/files", response_model=list[FileOut])
def get_files(collection_id: int, db: Session = Depends(get_db)):
    return collections_service.get_collection_files(db, collection_id)
