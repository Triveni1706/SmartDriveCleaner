from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class ScannedFile(Base):
    __tablename__ = "scanned_files"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    path = Column(String, unique=True, index=True)
    extension = Column(String, index=True)
    category = Column(String, index=True)  # Documents, Images, Videos, Audio, PDFs, Archives, Others
    size_bytes = Column(Integer)
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    accessed_at = Column(DateTime)
    sha256 = Column(String, index=True)
    is_duplicate = Column(Boolean, default=False)
    duplicate_group = Column(String, index=True, nullable=True)  # sha256 of the group

    # --- Phase 2 additions ---
    subcategory = Column(String, index=True, nullable=True)   # e.g. Resume, Invoice, Screenshot, Photo
    subcategory_confidence = Column(Float, nullable=True)      # 0-1, heuristic confidence
    is_blurry = Column(Boolean, nullable=True)                 # images only
    blur_score = Column(Float, nullable=True)                  # Laplacian variance (lower = blurrier)
    pdf_page_count = Column(Integer, nullable=True)
    pdf_author = Column(String, nullable=True)
    pdf_title = Column(String, nullable=True)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    archive_file_count = Column(Integer, nullable=True)
    archive_uncompressed_bytes = Column(Integer, nullable=True)
    perceptual_hash = Column(String, index=True, nullable=True)  # for near-duplicate images
    similar_group = Column(String, index=True, nullable=True)    # groups near-duplicate images

    # --- Phase 3: two-stage scan architecture ---
    # Quick scan (Stage 1) always sets these:
    scan_root = Column(String, index=True, nullable=True)     # root folder this file was last seen under
    last_seen_scan = Column(String, index=True, nullable=True)  # job id of the quick scan that last saw this file

    # Deep analysis (Stage 2) bookkeeping — lets us skip files that haven't
    # changed since they were last hashed/classified ("incremental scanning").
    analyzed_at = Column(DateTime, nullable=True)  # when deep analysis last ran for this file
    content_signature = Column(String, nullable=True)  # f"{size_bytes}:{modified_at.isoformat()}" at last analysis time


class ScanJob(Base):
    """Tracks a background quick-scan or deep-analysis run so the frontend
    can poll for progress (current task, percent complete, ETA)."""
    __tablename__ = "scan_jobs"

    id = Column(String, primary_key=True, index=True)  # uuid4 hex
    job_type = Column(String, index=True)  # quick_scan | deep_scan
    status = Column(String, index=True, default="pending")  # pending, running, completed, error
    root_path = Column(String, nullable=True)
    categories = Column(String, nullable=True)  # comma-separated, deep_scan only
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    current_task = Column(String, nullable=True)
    percent = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)
    result_json = Column(String, nullable=True)  # JSON-encoded result summary


class AuditLog(Base):
    """Every automated or scheduled action gets recorded here — scans,
    monitor start/stop, auto-rescans from file events, scheduled cleanups,
    and report generation. Powers the AI chat assistant's "what happened"
    answers and gives a real audit trail for a tool that deletes files."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String, index=True)  # scan, monitor_started, monitor_stopped, auto_rescan, scheduled_cleanup, report_generated, files_deleted
    detail = Column(String, nullable=True)


class TrashItem(Base):
    """Safe-delete bookkeeping. Files are moved (not removed) into a
    SmartDriveCleaner/Trash folder next to the original scan root, and a row
    here records enough to restore them or purge them for good later."""
    __tablename__ = "trash_items"

    id = Column(Integer, primary_key=True, index=True)
    original_path = Column(String, index=True)      # where the file lived
    trash_path = Column(String, index=True)          # where it lives now, inside Trash
    file_name = Column(String)
    extension = Column(String, nullable=True)
    category = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    deleted_at = Column(DateTime, default=datetime.utcnow, index=True)
    original_file_id = Column(Integer, nullable=True)  # ScannedFile.id at time of deletion, best-effort
    restored = Column(Boolean, default=False)


class Collection(Base):
    """User-defined groupings, e.g. 'Important PDFs', 'Certificates'."""
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CollectionFile(Base):
    """Many-to-many link between Collection and ScannedFile."""
    __tablename__ = "collection_files"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, index=True)
    file_id = Column(Integer, index=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class OrganizeLog(Base):
    """One row per file move performed by the Organizer. Powers Undo Last
    Organization (grouped by batch_id) and the organization-history feed."""
    __tablename__ = "organize_log"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String, index=True)          # groups all moves from one Organize run
    batch_type = Column(String, index=True)        # category_organize | merge_by_type | separate_files_folders
    old_path = Column(String)
    new_path = Column(String)
    category = Column(String, nullable=True)
    size_bytes = Column(Integer, default=0)
    is_folder = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    undone = Column(Boolean, default=False)


class OrganizeBatch(Base):
    """Summary row per Organize run, so /organization-history and dashboard
    metrics don't have to re-aggregate organize_log every time."""
    __tablename__ = "organize_batches"

    id = Column(String, primary_key=True, index=True)  # uuid4 hex, matches OrganizeLog.batch_id
    batch_type = Column(String, index=True)
    root_path = Column(String)
    files_moved = Column(Integer, default=0)
    folders_created = Column(Integer, default=0)
    duplicates_removed = Column(Integer, default=0)
    bytes_saved = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    undone = Column(Boolean, default=False)
    undone_at = Column(DateTime, nullable=True)


class ScheduledRun(Base):
    """History of scheduler executions (daily/weekly/monthly cleanup jobs)."""
    __tablename__ = "scheduled_runs"

    id = Column(Integer, primary_key=True, index=True)
    ran_at = Column(DateTime, default=datetime.utcnow, index=True)
    job_name = Column(String, index=True)  # e.g. "daily_duplicate_cleanup"
    frequency = Column(String)  # daily, weekly, monthly
    files_affected = Column(Integer, default=0)
    bytes_recovered = Column(Integer, default=0)
    detail = Column(String, nullable=True)
