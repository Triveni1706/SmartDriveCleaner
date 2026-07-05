"""
Organizer: turns Smart Drive Cleaner from a read-only analyzer into a real
file organizer. Every operation here calls shutil.move() (or os.rmdir/
os.remove with explicit confirmation) directly against the real filesystem,
so results are immediately visible in Windows Explorer — there is no
virtual/staged filesystem layer.

Safety model:
- Nothing destructive happens without a preceding preview step returning
  the same plan the user approves.
- Every move is logged to OrganizeLog *before* it is executed, batched under
  a batch_id, so "Undo Last Organization" can always walk the log backwards
  and restore files even if the process crashes mid-run.
- Windows system folders, hidden files, and known OS/program directories are
  skipped by default.
- Duplicate deletion always requires an explicit confirmed file id list; nothing
  is ever deleted purely from a scan/preview.
"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from database.models import OrganizeLog, OrganizeBatch, AuditLog

# --- Category rules (per spec) ---

CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "Documents": {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".txt"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov"},
    "Audio": {".mp3", ".wav", ".flac"},
    "Archives": {".zip", ".rar", ".7z"},
    "Applications": {".exe", ".msi"},
    "Code": {".py", ".js", ".ts", ".java", ".cpp", ".html", ".css"},
}
OTHERS_CATEGORY = "Others"
CATEGORY_ORDER = ["Images", "Documents", "Videos", "Audio", "Archives", "Applications", "Code", OTHERS_CATEGORY]

ORGANIZED_ROOT_NAME = "Organized"
FILES_FOLDER_NAME = "Files"
FOLDERS_FOLDER_NAME = "Folders"

# --- Safety: never touch these ---

WINDOWS_SYSTEM_DIR_NAMES = {
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "recovery",
    "appdata", "msocache", "perflogs", "boot",
}
APP_OWNED_DIR_NAMES = {"smartdrivecleaner_trash"}


class OrganizerError(Exception):
    pass


def categorize_extension(ext: str) -> str:
    ext = ext.lower()
    for category, exts in CATEGORY_EXTENSIONS.items():
        if ext in exts:
            return category
    return OTHERS_CATEGORY


def is_hidden(path: str) -> bool:
    name = os.path.basename(path.rstrip(os.sep))
    if name.startswith("."):
        return True
    if platform.system() == "Windows":
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
            FILE_ATTRIBUTE_HIDDEN = 0x2
            FILE_ATTRIBUTE_SYSTEM = 0x4
            if attrs != -1 and (attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM)):
                return True
        except Exception:
            pass
    return False


def is_system_path(path: str) -> bool:
    """Skip Windows folder, Program Files, other OS-critical directories, and
    the app's own working directories (Trash / Organized), so the organizer
    never reorganizes itself or the OS."""
    parts = [p.lower() for p in Path(path).parts]
    for p in parts:
        if p in WINDOWS_SYSTEM_DIR_NAMES or p in APP_OWNED_DIR_NAMES:
            return True
    return False


def should_skip(path: str, include_hidden: bool = False) -> bool:
    if is_system_path(path):
        return True
    if not include_hidden and is_hidden(path):
        return True
    return False


def sha256_of(path: str, chunk_size: int = 65536, max_bytes: int = 200 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_bytes:
                h.update(f.read(50 * 1024 * 1024))
            else:
                while chunk := f.read(chunk_size):
                    h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return ""


def _unique_destination(dest_dir: str, filename: str) -> str:
    """Avoids clobbering an existing file at the destination by appending
    ' (2)', ' (3)', etc. Never silently overwrites."""
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    base, ext = os.path.splitext(filename)
    n = 2
    while True:
        candidate = os.path.join(dest_dir, f"{base} ({n}){ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _list_top_level_entries(root: str, include_hidden: bool) -> list[str]:
    entries = []
    with os.scandir(root) as it:
        for entry in it:
            full = entry.path
            if should_skip(full, include_hidden):
                continue
            entries.append(full)
    return entries


# --- 1 & 2: Category-based organization ---

def plan_category_organize(root: str, include_hidden: bool = False) -> dict:
    """Preview: returns the move plan without touching disk."""
    if not os.path.isdir(root):
        raise OrganizerError(f"Not a directory: {root}")

    moves = []
    for entry_path in _list_top_level_entries(root, include_hidden):
        if os.path.isdir(entry_path):
            continue  # category organize only moves loose files at top level
        ext = os.path.splitext(entry_path)[1]
        category = categorize_extension(ext)
        dest_dir = os.path.join(root, ORGANIZED_ROOT_NAME, category)
        dest_path = os.path.join(dest_dir, os.path.basename(entry_path))
        moves.append({
            "current_path": entry_path,
            "new_path": dest_path,
            "category": category,
            "size_bytes": _safe_size(entry_path),
        })
    folders_to_create = sorted({os.path.join(root, ORGANIZED_ROOT_NAME, c) for c in CATEGORY_ORDER})
    return {"root": root, "moves": moves, "folders_to_create": folders_to_create}


def execute_category_organize(db: Session, root: str, include_hidden: bool = False) -> dict:
    plan = plan_category_organize(root, include_hidden)
    return _execute_moves(db, plan["moves"], batch_type="category_organize", root=root,
                           folders_to_create=plan["folders_to_create"])


# --- 3: Merge Files by Type (in-place, same folder, no "Organized" wrapper) ---

def plan_merge_by_type(root: str, include_hidden: bool = False) -> dict:
    if not os.path.isdir(root):
        raise OrganizerError(f"Not a directory: {root}")

    moves = []
    categories_seen: set[str] = set()
    for entry_path in _list_top_level_entries(root, include_hidden):
        if os.path.isdir(entry_path):
            continue
        ext = os.path.splitext(entry_path)[1]
        category = categorize_extension(ext)
        categories_seen.add(category)
        dest_dir = os.path.join(root, category)
        dest_path = os.path.join(dest_dir, os.path.basename(entry_path))
        moves.append({
            "current_path": entry_path,
            "new_path": dest_path,
            "category": category,
            "size_bytes": _safe_size(entry_path),
        })
    folders_to_create = sorted(os.path.join(root, c) for c in categories_seen)
    return {"root": root, "moves": moves, "folders_to_create": folders_to_create}


def execute_merge_by_type(db: Session, root: str, include_hidden: bool = False) -> dict:
    plan = plan_merge_by_type(root, include_hidden)
    return _execute_moves(db, plan["moves"], batch_type="merge_by_type", root=root,
                           folders_to_create=plan["folders_to_create"])


# --- 4: Separate Files and Folders ---

def plan_separate_files_folders(root: str, include_hidden: bool = False) -> dict:
    if not os.path.isdir(root):
        raise OrganizerError(f"Not a directory: {root}")

    moves = []
    for entry_path in _list_top_level_entries(root, include_hidden):
        is_dir = os.path.isdir(entry_path)
        if is_dir and os.path.basename(entry_path) in (FILES_FOLDER_NAME, FOLDERS_FOLDER_NAME):
            continue  # don't re-move our own output folders
        bucket = FOLDERS_FOLDER_NAME if is_dir else FILES_FOLDER_NAME
        dest_dir = os.path.join(root, bucket)
        dest_path = os.path.join(dest_dir, os.path.basename(entry_path))
        moves.append({
            "current_path": entry_path,
            "new_path": dest_path,
            "category": bucket,
            "size_bytes": _safe_size(entry_path) if not is_dir else 0,
            "is_folder": is_dir,
        })
    folders_to_create = [os.path.join(root, FILES_FOLDER_NAME), os.path.join(root, FOLDERS_FOLDER_NAME)]
    return {"root": root, "moves": moves, "folders_to_create": folders_to_create}


def execute_separate_files_folders(db: Session, root: str, include_hidden: bool = False) -> dict:
    plan = plan_separate_files_folders(root, include_hidden)
    return _execute_moves(db, plan["moves"], batch_type="separate_files_folders", root=root,
                           folders_to_create=plan["folders_to_create"])


# --- shared move executor (creates folders, logs, then shutil.move) ---

def _safe_size(path: str) -> int:
    try:
        return os.path.getsize(path) if os.path.isfile(path) else 0
    except OSError:
        return 0


def _execute_moves(db: Session, moves: list[dict], batch_type: str, root: str,
                    folders_to_create: list[str]) -> dict:
    batch_id = uuid.uuid4().hex
    created_dirs: set[str] = set()

    for d in folders_to_create:
        os.makedirs(d, exist_ok=True)
        created_dirs.add(d)

    moved_count = 0
    failed = []
    total_bytes = 0

    for m in moves:
        src = m["current_path"]
        try:
            if not os.path.exists(src):
                raise OrganizerError("Source no longer exists")
            dest_dir = os.path.dirname(m["new_path"])
            os.makedirs(dest_dir, exist_ok=True)
            created_dirs.add(dest_dir)
            final_dest = _unique_destination(dest_dir, os.path.basename(m["new_path"])) \
                if os.path.exists(m["new_path"]) else m["new_path"]

            # Log BEFORE moving so undo is always possible, even on crash mid-batch.
            db.add(OrganizeLog(
                batch_id=batch_id,
                batch_type=batch_type,
                old_path=src,
                new_path=final_dest,
                category=m.get("category"),
                size_bytes=m.get("size_bytes", 0),
                is_folder=bool(m.get("is_folder", False)),
            ))
            db.commit()

            shutil.move(src, final_dest)
            moved_count += 1
            total_bytes += m.get("size_bytes", 0)
        except (OSError, OrganizerError) as e:
            failed.append({"path": src, "error": str(e)})

    batch = OrganizeBatch(
        id=batch_id,
        batch_type=batch_type,
        root_path=root,
        files_moved=moved_count,
        folders_created=len(created_dirs),
        duplicates_removed=0,
        bytes_saved=0,
    )
    db.add(batch)
    db.add(AuditLog(action="organize_run", detail=f"{batch_type}: {moved_count} moved under {root}"))
    db.commit()

    return {
        "batch_id": batch_id,
        "moved": moved_count,
        "folders_created": len(created_dirs),
        "failed": failed,
    }


# --- 5: Smart Duplicate Cleanup ---

def find_duplicates(root: str, include_hidden: bool = False) -> list[dict]:
    """Walks the tree, hashes every file, groups by sha256. Returns groups
    with 2+ members; the newest-modified file in each group is suggested to
    keep, but nothing is deleted here — this is preview-only."""
    if not os.path.isdir(root):
        raise OrganizerError(f"Not a directory: {root}")

    by_hash: dict[str, list[dict]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if should_skip(dirpath, include_hidden):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not should_skip(os.path.join(dirpath, d), include_hidden)]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if should_skip(full, include_hidden):
                continue
            try:
                size = os.path.getsize(full)
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            if size == 0:
                continue
            digest = sha256_of(full)
            if not digest:
                continue
            by_hash.setdefault(digest, []).append({
                "path": full, "size_bytes": size, "modified_at": mtime,
            })

    groups = []
    for digest, members in by_hash.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda m: m["modified_at"], reverse=True)
        groups.append({
            "sha256": digest,
            "size_bytes": members[0]["size_bytes"],
            "keep_suggestion": members[0]["path"],
            "files": members,
            "wasted_bytes": members[0]["size_bytes"] * (len(members) - 1),
        })
    groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)
    return groups


def delete_confirmed_duplicates(db: Session, file_paths: list[str]) -> dict:
    """Only ever called after explicit user confirmation of a specific path
    list (never a whole group blindly) — deletes those exact files."""
    deleted, failed = [], []
    total_bytes = 0
    for path in file_paths:
        try:
            if should_skip(path):
                raise OrganizerError("Refusing to delete a system/hidden path")
            if not os.path.isfile(path):
                raise OrganizerError("Not a file or no longer exists")
            size = os.path.getsize(path)
            os.remove(path)
            deleted.append(path)
            total_bytes += size
        except (OSError, OrganizerError) as e:
            failed.append({"path": path, "error": str(e)})

    if deleted:
        db.add(AuditLog(action="duplicates_deleted", detail=f"{len(deleted)} duplicate file(s) removed"))
        # Track under a synthetic batch purely for dashboard metrics.
        db.add(OrganizeBatch(
            id=uuid.uuid4().hex,
            batch_type="duplicate_cleanup",
            root_path=os.path.dirname(deleted[0]) if deleted else "",
            files_moved=0,
            folders_created=0,
            duplicates_removed=len(deleted),
            bytes_saved=total_bytes,
        ))
        db.commit()
    return {"deleted": deleted, "failed": failed, "bytes_saved": total_bytes}


# --- 6: Undo ---

def undo_batch(db: Session, batch_id: str) -> dict:
    batch = db.query(OrganizeBatch).filter(OrganizeBatch.id == batch_id, OrganizeBatch.undone == False).first()  # noqa: E712
    if not batch:
        raise OrganizerError("Batch not found or already undone")

    logs = (
        db.query(OrganizeLog)
        .filter(OrganizeLog.batch_id == batch_id, OrganizeLog.undone == False)  # noqa: E712
        .order_by(OrganizeLog.id.desc())
        .all()
    )
    restored, failed = [], []
    for log in logs:
        try:
            if not os.path.exists(log.new_path):
                raise OrganizerError("Moved file no longer exists at its new location")
            os.makedirs(os.path.dirname(log.old_path), exist_ok=True)
            target = log.old_path
            if os.path.exists(target):
                target = _unique_destination(os.path.dirname(target), os.path.basename(target))
            shutil.move(log.new_path, target)
            log.undone = True
            restored.append({"old_path": target, "new_path": log.new_path})
        except (OSError, OrganizerError) as e:
            failed.append({"path": log.new_path, "error": str(e)})

    batch.undone = True
    batch.undone_at = datetime.utcnow()
    db.add(AuditLog(action="organize_undo", detail=f"Undid batch {batch_id}: {len(restored)} restored"))
    db.commit()
    return {"batch_id": batch_id, "restored": len(restored), "failed": failed}


def latest_undoable_batch(db: Session) -> OrganizeBatch | None:
    return (
        db.query(OrganizeBatch)
        .filter(OrganizeBatch.undone == False)  # noqa: E712
        .order_by(OrganizeBatch.created_at.desc())
        .first()
    )


# --- 7: Empty folder cleanup (reuses same semantics as file_ops, but
# system-folder aware) ---

def find_empty_folders(root: str, limit: int = 500) -> list[dict]:
    if not root or not os.path.isdir(root):
        return []
    empty_dirs: list[dict] = []
    is_empty_cache: dict[str, bool] = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        if is_system_path(dirpath):
            is_empty_cache[dirpath] = False
            continue
        has_files = len(filenames) > 0
        all_subdirs_empty = all(is_empty_cache.get(os.path.join(dirpath, d), False) for d in dirnames)
        empty = (not has_files) and (all_subdirs_empty if dirnames else True)
        is_empty_cache[dirpath] = empty
        if empty and dirpath != root:
            empty_dirs.append({"path": dirpath})
            if len(empty_dirs) >= limit:
                break
    return empty_dirs


def delete_empty_folders(paths: list[str]) -> dict:
    deleted, failed = [], []
    for p in paths:
        try:
            if is_system_path(p):
                raise OrganizerError("Refusing to remove a system folder")
            if os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p)
                deleted.append(p)
            else:
                failed.append({"path": p, "error": "Not empty or not found"})
        except (OSError, OrganizerError) as e:
            failed.append({"path": p, "error": str(e)})
    return {"deleted": deleted, "failed": failed}


# --- 9: Real-time auto-organize hook (called from services/monitor.py) ---

def auto_organize_new_file(db: Session, path: str, watch_root: str) -> dict | None:
    """Moves a single newly-created file straight into
    <watch_root>/Organized/<Category>/ the moment the monitor sees it.
    Returns the move record, or None if the file was skipped/already
    inside an Organized/Trash folder (to avoid re-triggering on our own moves)."""
    if should_skip(path) or not os.path.isfile(path):
        return None
    if ORGANIZED_ROOT_NAME.lower() in [p.lower() for p in Path(path).parts]:
        return None  # already organized, or is the destination of a prior move

    ext = os.path.splitext(path)[1]
    category = categorize_extension(ext)
    dest_dir = os.path.join(watch_root, ORGANIZED_ROOT_NAME, category)
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = _unique_destination(dest_dir, os.path.basename(path))

    batch_id = uuid.uuid4().hex
    db.add(OrganizeLog(
        batch_id=batch_id, batch_type="auto_monitor", old_path=path,
        new_path=dest_path, category=category, size_bytes=_safe_size(path),
    ))
    db.add(OrganizeBatch(
        id=batch_id, batch_type="auto_monitor", root_path=watch_root,
        files_moved=1, folders_created=0, duplicates_removed=0, bytes_saved=0,
    ))
    db.commit()

    shutil.move(path, dest_path)
    db.add(AuditLog(action="auto_organize", detail=f"{path} -> {dest_path}"))
    db.commit()
    return {"old_path": path, "new_path": dest_path, "category": category}


# --- 10: Dashboard metrics ---

def get_stats(db: Session) -> dict:
    from sqlalchemy import func

    total_files_moved = db.query(func.coalesce(func.sum(OrganizeBatch.files_moved), 0)).scalar() or 0
    total_folders_created = db.query(func.coalesce(func.sum(OrganizeBatch.folders_created), 0)).scalar() or 0
    total_duplicates_removed = db.query(func.coalesce(func.sum(OrganizeBatch.duplicates_removed), 0)).scalar() or 0
    total_bytes_saved = db.query(func.coalesce(func.sum(OrganizeBatch.bytes_saved), 0)).scalar() or 0
    total_runs = db.query(func.count(OrganizeBatch.id)).scalar() or 0

    return {
        "files_moved": int(total_files_moved),
        "folders_created": int(total_folders_created),
        "duplicates_removed": int(total_duplicates_removed),
        "space_saved_bytes": int(total_bytes_saved),
        "organize_runs": int(total_runs),
    }
