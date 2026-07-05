"""
Real-time monitoring: watches a scanned root folder for filesystem changes
and automatically re-scans affected files, instead of requiring a manual
"Scan folder" click every time. Uses the `watchdog` library (real OS-level
file events via inotify/ReadDirectoryChangesW/FSEvents — not polling).

Design:
- One watched root at a time (matches the single-location scan model).
- File events are debounced: rapid-fire events (e.g. a large copy operation)
  are batched and processed a short delay after things go quiet, instead of
  re-scanning on every single event.
- Runs in a background thread owned by the FastAPI app lifecycle, with its
  own short-lived DB session per batch (safe with SQLite's check_same_thread
  disabled in database/db.py).
"""
import os
import threading
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from database.db import SessionLocal
from database.models import ScannedFile, AuditLog
from services.scanner import categorize, compute_sha256, scan_single_file
from services import organizer

DEBOUNCE_SECONDS = 2.0


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(self, on_settled):
        self._on_settled = on_settled
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._dirty_paths: set[str] = set()
        self._removed_paths: set[str] = set()

    def _schedule(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_SECONDS, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self):
        with self._lock:
            dirty, removed = list(self._dirty_paths), list(self._removed_paths)
            self._dirty_paths.clear()
            self._removed_paths.clear()
        if dirty or removed:
            self._on_settled(dirty, removed)

    def on_created(self, event):
        if not event.is_directory:
            with self._lock:
                self._dirty_paths.add(event.src_path)
            self._schedule()

    def on_modified(self, event):
        if not event.is_directory:
            with self._lock:
                self._dirty_paths.add(event.src_path)
            self._schedule()

    def on_deleted(self, event):
        if not event.is_directory:
            with self._lock:
                self._removed_paths.add(event.src_path)
            self._schedule()

    def on_moved(self, event):
        if not event.is_directory:
            with self._lock:
                self._removed_paths.add(event.src_path)
                self._dirty_paths.add(event.dest_path)
            self._schedule()


class DriveMonitor:
    """Singleton-style controller: only one root watched at a time."""

    def __init__(self):
        self._observer: Observer | None = None
        self._root: str | None = None
        self._status = "stopped"  # stopped | watching | error
        self._last_event_at: float | None = None
        self._events_processed = 0
        self._error: str | None = None
        self._auto_organize = False
        self._auto_organized_count = 0

    def start(self, root_path: str, auto_organize: bool = False):
        self.stop()
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {root_path}")

        handler = _DebouncedHandler(self._handle_batch)
        observer = Observer()
        observer.schedule(handler, str(root), recursive=True)
        observer.start()

        self._observer = observer
        self._root = str(root)
        self._status = "watching"
        self._error = None
        self._auto_organize = auto_organize
        self._auto_organized_count = 0
        self._log("monitor_started", f"Started watching {root}" + (" (auto-organize on)" if auto_organize else ""))

    def stop(self):
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=3)
            except Exception:
                pass
        if self._root:
            self._log("monitor_stopped", f"Stopped watching {self._root}")
        self._observer = None
        self._root = None
        self._status = "stopped"

    def status(self) -> dict:
        return {
            "status": self._status,
            "root": self._root,
            "last_event_at": self._last_event_at,
            "events_processed": self._events_processed,
            "error": self._error,
            "auto_organize": self._auto_organize,
            "auto_organized_count": self._auto_organized_count,
        }

    def _log(self, action: str, detail: str):
        db = SessionLocal()
        try:
            db.add(AuditLog(action=action, detail=detail))
            db.commit()
        finally:
            db.close()

    def _handle_batch(self, dirty_paths: list[str], removed_paths: list[str]):
        self._last_event_at = time.time()
        db = SessionLocal()
        try:
            for path in removed_paths:
                db.query(ScannedFile).filter(ScannedFile.path == path).delete(synchronize_session=False)

            for path in dirty_paths:
                if not os.path.exists(path):
                    continue

                effective_path = path
                if self._auto_organize and self._root:
                    try:
                        moved = organizer.auto_organize_new_file(db, path, self._root)
                        if moved:
                            effective_path = moved["new_path"]
                            self._auto_organized_count += 1
                    except Exception:
                        pass  # never let an organize failure break indexing

                if not os.path.exists(effective_path):
                    continue
                try:
                    record = scan_single_file(effective_path)
                except Exception:
                    continue
                existing = db.query(ScannedFile).filter(ScannedFile.path == effective_path).first()
                if existing:
                    for key, value in record.items():
                        setattr(existing, key, value)
                else:
                    db.add(ScannedFile(**record))

            db.commit()
            self._events_processed += len(dirty_paths) + len(removed_paths)
            if dirty_paths or removed_paths:
                db.add(AuditLog(
                    action="auto_rescan",
                    detail=f"{len(dirty_paths)} updated, {len(removed_paths)} removed",
                ))
                db.commit()
        except Exception as e:
            self._status = "error"
            self._error = str(e)
        finally:
            db.close()


monitor = DriveMonitor()
