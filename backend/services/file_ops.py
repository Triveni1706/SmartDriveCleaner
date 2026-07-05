"""
Direct file management — everything the spec calls "Direct File Management"
plus the "Safe Delete System": open/open-folder, rename, move, copy, and a
trash-based delete/restore/purge flow instead of immediate os.remove().

All operations act on the real filesystem (this is a local scanning tool,
not a cloud drive), and every mutating operation updates ScannedFile rows
in-place so the DB stays in sync without a full rescan.
"""
import os
import platform
import shutil
import subprocess
from datetime import datetime

from sqlalchemy.orm import Session

from database.models import ScannedFile, TrashItem, AuditLog

TRASH_DIRNAME = "SmartDriveCleaner_Trash"


class FileOpError(Exception):
    pass


def _get_file(db: Session, file_id: int) -> ScannedFile:
    f = db.query(ScannedFile).filter(ScannedFile.id == file_id).first()
    if not f:
        raise FileOpError(f"File {file_id} not found in index")
    if not os.path.exists(f.path):
        raise FileOpError(f"File no longer exists on disk: {f.path}")
    return f


# --- Open (server-side default-app open; this app runs against a local drive) ---

def open_file(path: str):
    if not os.path.exists(path):
        raise FileOpError(f"Path does not exist: {path}")
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        raise FileOpError(f"Could not open {path}: {e}")


def open_containing_folder(path: str):
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    open_file(folder)


# --- Rename / Move / Copy ---

def rename_file(db: Session, file_id: int, new_name: str) -> ScannedFile:
    f = _get_file(db, file_id)
    if os.sep in new_name or (os.altsep and os.altsep in new_name):
        raise FileOpError("New name must not contain path separators")
    new_path = os.path.join(os.path.dirname(f.path), new_name)
    if os.path.exists(new_path):
        raise FileOpError(f"A file named '{new_name}' already exists there")
    os.rename(f.path, new_path)
    f.path = new_path
    f.name = new_name
    f.extension = os.path.splitext(new_name)[1].lower()
    db.add(AuditLog(action="file_renamed", detail=f"{file_id}: -> {new_name}"))
    db.commit()
    db.refresh(f)
    return f


def move_file(db: Session, file_id: int, destination_folder: str) -> ScannedFile:
    f = _get_file(db, file_id)
    if not os.path.isdir(destination_folder):
        raise FileOpError(f"Destination folder does not exist: {destination_folder}")
    new_path = os.path.join(destination_folder, f.name)
    if os.path.exists(new_path):
        raise FileOpError(f"A file named '{f.name}' already exists at destination")
    shutil.move(f.path, new_path)
    old_path = f.path
    f.path = new_path
    db.add(AuditLog(action="file_moved", detail=f"{file_id}: {old_path} -> {new_path}"))
    db.commit()
    db.refresh(f)
    return f


def copy_file(db: Session, file_id: int, destination_folder: str) -> ScannedFile:
    f = _get_file(db, file_id)
    if not os.path.isdir(destination_folder):
        raise FileOpError(f"Destination folder does not exist: {destination_folder}")
    new_path = os.path.join(destination_folder, f.name)
    if os.path.exists(new_path):
        base, ext = os.path.splitext(f.name)
        new_path = os.path.join(destination_folder, f"{base} (copy){ext}")
    shutil.copy2(f.path, new_path)

    copy_row = ScannedFile(
        name=os.path.basename(new_path),
        path=new_path,
        extension=f.extension,
        category=f.category,
        size_bytes=f.size_bytes,
        created_at=datetime.utcnow(),
        modified_at=f.modified_at,
        accessed_at=f.accessed_at,
        sha256=f.sha256,
        is_duplicate=True,
        duplicate_group=f.sha256,
        scan_root=f.scan_root,
    )
    db.add(copy_row)
    db.add(AuditLog(action="file_copied", detail=f"{file_id}: {f.path} -> {new_path}"))
    db.commit()
    db.refresh(copy_row)
    return copy_row


def bulk_delete_permanent_from_trash(trash_root: str):
    pass  # kept out — permanent purge lives in empty_trash() below


# --- Safe Delete / Trash / Recovery ---

def _trash_root_for(path: str, scan_root: str | None = None) -> str:
    """Trash lives at SmartDriveCleaner_Trash under the file's scan root
    (one place per scanned drive/folder, matching the spec's
    'SmartDriveCleaner/Trash' layout) — falling back to the file's own
    drive/directory if no scan root is known."""
    base = scan_root if scan_root and os.path.isdir(scan_root) else None
    if not base:
        drive_root = os.path.splitdrive(path)[0]
        base = drive_root if drive_root and os.path.isdir(drive_root) else os.path.dirname(path)
    trash_dir = os.path.join(base, TRASH_DIRNAME)
    os.makedirs(trash_dir, exist_ok=True)
    return trash_dir


def soft_delete_files(db: Session, file_ids: list[int]) -> dict:
    """Moves files into the Trash folder instead of deleting them, and
    records a TrashItem so they can be restored later."""
    deleted, failed = [], []
    files = db.query(ScannedFile).filter(ScannedFile.id.in_(file_ids)).all()
    for f in files:
        try:
            if not os.path.exists(f.path):
                raise FileOpError("File missing on disk")
            trash_dir = _trash_root_for(f.path, f.scan_root)
            trash_name = f"{f.id}_{f.name}"
            trash_path = os.path.join(trash_dir, trash_name)
            shutil.move(f.path, trash_path)

            db.add(TrashItem(
                original_path=f.path,
                trash_path=trash_path,
                file_name=f.name,
                extension=f.extension,
                category=f.category,
                size_bytes=f.size_bytes or 0,
                original_file_id=f.id,
            ))
            db.delete(f)
            deleted.append(f.id)
        except (OSError, FileOpError) as e:
            failed.append({"id": f.id, "error": str(e)})
    if deleted:
        db.add(AuditLog(action="files_trashed", detail=f"{len(deleted)} file(s) moved to trash"))
    db.commit()
    return {"deleted": deleted, "failed": failed}


def list_trash(db: Session) -> list[TrashItem]:
    return db.query(TrashItem).filter(TrashItem.restored == False).order_by(TrashItem.deleted_at.desc()).all()  # noqa: E712


def restore_files(db: Session, trash_ids: list[int]) -> dict:
    restored, failed = [], []
    items = db.query(TrashItem).filter(TrashItem.id.in_(trash_ids), TrashItem.restored == False).all()  # noqa: E712
    for item in items:
        try:
            if not os.path.exists(item.trash_path):
                raise FileOpError("Trashed file missing on disk")
            os.makedirs(os.path.dirname(item.original_path), exist_ok=True)
            target = item.original_path
            if os.path.exists(target):
                base, ext = os.path.splitext(target)
                target = f"{base} (restored){ext}"
            shutil.move(item.trash_path, target)
            item.restored = True

            db.add(ScannedFile(
                name=os.path.basename(target),
                path=target,
                extension=item.extension,
                category=item.category,
                size_bytes=item.size_bytes,
                created_at=datetime.utcnow(),
                modified_at=datetime.utcnow(),
                sha256="",
            ))
            restored.append(item.id)
        except (OSError, FileOpError) as e:
            failed.append({"id": item.id, "error": str(e)})
    if restored:
        db.add(AuditLog(action="files_restored", detail=f"{len(restored)} file(s) restored from trash"))
    db.commit()
    return {"restored": restored, "failed": failed}


def purge_trash(db: Session, trash_ids: list[int] | None = None) -> dict:
    """Permanently deletes items from the trash (from disk and the DB).
    If trash_ids is None, empties the whole trash."""
    query = db.query(TrashItem).filter(TrashItem.restored == False)  # noqa: E712
    if trash_ids is not None:
        query = query.filter(TrashItem.id.in_(trash_ids))
    items = query.all()
    purged, failed = [], []
    for item in items:
        try:
            if os.path.exists(item.trash_path):
                os.remove(item.trash_path)
            db.delete(item)
            purged.append(item.id)
        except OSError as e:
            failed.append({"id": item.id, "error": str(e)})
    if purged:
        db.add(AuditLog(action="trash_purged", detail=f"{len(purged)} file(s) permanently deleted"))
    db.commit()
    return {"purged": purged, "failed": failed}


# --- Empty folder detection ---

def find_empty_folders(scan_root: str, limit: int = 500) -> list[dict]:
    """Bottom-up walk: a folder is empty if it has no files and every
    subfolder is itself (transitively) empty. Skips the app's own Trash dir."""
    if not scan_root or not os.path.isdir(scan_root):
        return []

    empty_dirs: list[dict] = []
    is_empty_cache: dict[str, bool] = {}

    for dirpath, dirnames, filenames in os.walk(scan_root, topdown=False):
        if os.path.basename(dirpath) == TRASH_DIRNAME:
            is_empty_cache[dirpath] = False
            continue
        has_files = len(filenames) > 0
        all_subdirs_empty = all(
            is_empty_cache.get(os.path.join(dirpath, d), False) for d in dirnames
        )
        empty = (not has_files) and (all_subdirs_empty if dirnames else True)
        is_empty_cache[dirpath] = empty
        if empty and dirpath != scan_root:
            try:
                size_note = 0
            except OSError:
                size_note = 0
            empty_dirs.append({"path": dirpath, "size_bytes": size_note})
            if len(empty_dirs) >= limit:
                break

    return empty_dirs


def delete_empty_folders(paths: list[str]) -> dict:
    deleted, failed = [], []
    for p in paths:
        try:
            if os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p)
                deleted.append(p)
            else:
                failed.append({"path": p, "error": "Not empty or not found"})
        except OSError as e:
            failed.append({"path": p, "error": str(e)})
    return {"deleted": deleted, "failed": failed}
