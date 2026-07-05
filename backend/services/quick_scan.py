"""
Stage 1 — Quick Scan.

Walks a folder/drive and records ONLY filesystem metadata (name, extension,
size, path, created/modified dates). No hashing, no PDF/image opening, no AI
models, no duplicate detection — that's all Stage 2 (deep_analysis.py), run
only for the categories the user opts into.

Incremental: files whose size+modified_at haven't changed since the last
scan are left alone (their existing Stage 2 analysis, if any, is still
valid). Files that disappeared from disk since the last scan of this root
are removed from the database.
"""
import os
import time
from datetime import datetime
from pathlib import Path

from database.db import SessionLocal
from database.models import ScannedFile
from services.scanner import categorize, EXTENSION_MAP
from services import job_manager

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
PROGRESS_EVERY = 200  # DB write + job update cadence


def _category_stats(db, root_path: str) -> dict:
    from sqlalchemy import func

    rows = (
        db.query(ScannedFile.category, func.count(ScannedFile.id), func.sum(ScannedFile.size_bytes))
        .filter(ScannedFile.scan_root == root_path)
        .group_by(ScannedFile.category)
        .all()
    )
    stats = {}
    for category, count, size in rows:
        stats[category] = {"count": count, "bytes": size or 0}
    return stats


def run_quick_scan(job_id: str, root_path: str):
    db = SessionLocal()
    try:
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            job_manager.finish_job(job_id, status="error", error=f"Path does not exist or is not a directory: {root_path}")
            return

        job_manager.update_job(job_id, status="running", current_task="Scanning files (metadata only)…")

        # Preload existing rows for this root so we can decide add/update/skip
        # in memory instead of hitting the DB once per file.
        existing = {
            row.path: row
            for row in db.query(ScannedFile).all()
        }

        scanned_count = 0
        new_count = 0
        updated_count = 0
        unchanged_count = 0
        total_bytes = 0
        seen_paths: set[str] = set()
        last_update = time.perf_counter()

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    stat = os.stat(full_path)
                except (PermissionError, OSError, FileNotFoundError):
                    continue

                seen_paths.add(full_path)
                scanned_count += 1
                total_bytes += stat.st_size
                modified_at = datetime.fromtimestamp(stat.st_mtime)

                prior = existing.get(full_path)
                if prior is not None and prior.size_bytes == stat.st_size and prior.modified_at == modified_at:
                    # Unchanged since last scan — leave Stage 2 analysis intact.
                    prior.last_seen_scan = job_id
                    prior.scan_root = root_path
                    unchanged_count += 1
                else:
                    ext = Path(filename).suffix
                    category = categorize(ext)
                    if prior is not None:
                        # Content changed — stale any prior deep-analysis results.
                        prior.size_bytes = stat.st_size
                        prior.modified_at = modified_at
                        prior.created_at = datetime.fromtimestamp(stat.st_ctime)
                        prior.extension = ext
                        prior.category = category
                        prior.last_seen_scan = job_id
                        prior.analyzed_at = None
                        prior.content_signature = None
                        updated_count += 1
                    else:
                        record = ScannedFile(
                            name=filename,
                            path=full_path,
                            extension=ext,
                            category=category,
                            size_bytes=stat.st_size,
                            created_at=datetime.fromtimestamp(stat.st_ctime),
                            modified_at=modified_at,
                            accessed_at=datetime.fromtimestamp(stat.st_atime),
                            sha256="",
                            is_duplicate=False,
                            scan_root=root_path,
                            last_seen_scan=job_id,
                        )
                        db.add(record)
                        existing[full_path] = record
                        new_count += 1

                if scanned_count % PROGRESS_EVERY == 0:
                    db.commit()
                    now = time.perf_counter()
                    if now - last_update > 0.3:  # throttle job-row writes
                        job_manager.update_job(
                            job_id,
                            completed_items=scanned_count,
                            current_task=f"Scanning… {scanned_count:,} files found",
                        )
                        last_update = now

        db.commit()

        # Anything under this root not seen in this walk was deleted/moved.
        stale = [row for path, row in existing.items() if path not in seen_paths]
        for row in stale:
            db.delete(row)
        db.commit()

        stats = _category_stats(db, root_path)

        job_manager.update_job(job_id, completed_items=scanned_count, total_items=scanned_count)
        job_manager.finish_job(
            job_id,
            status="completed",
            result={
                "root_path": root_path,
                "scanned_files": scanned_count,
                "new_files": new_count,
                "updated_files": updated_count,
                "unchanged_files": unchanged_count,
                "removed_files": len(stale),
                "total_bytes": total_bytes,
                "by_category": stats,
            },
        )
    except Exception as e:  # noqa: BLE001 - background job, must never crash silently
        db.rollback()
        job_manager.finish_job(job_id, status="error", error=str(e))
    finally:
        db.close()
