from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ScanRequest(BaseModel):
    path: str


class ScanResult(BaseModel):
    scanned_files: int
    total_bytes: int
    duplicate_groups: int
    duplicate_wasted_bytes: int
    similar_image_groups: int = 0


class FileOut(BaseModel):
    id: int
    name: str
    path: str
    extension: str
    category: str
    size_bytes: int
    created_at: Optional[datetime]
    modified_at: Optional[datetime]
    accessed_at: Optional[datetime]
    sha256: str
    is_duplicate: bool
    duplicate_group: Optional[str]

    # Phase 2
    subcategory: Optional[str] = None
    subcategory_confidence: Optional[float] = None
    is_blurry: Optional[bool] = None
    blur_score: Optional[float] = None
    pdf_page_count: Optional[int] = None
    pdf_author: Optional[str] = None
    pdf_title: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    archive_file_count: Optional[int] = None
    archive_uncompressed_bytes: Optional[int] = None
    perceptual_hash: Optional[str] = None
    similar_group: Optional[str] = None

    class Config:
        from_attributes = True


class StorageStats(BaseModel):
    total_files: int
    total_bytes: int
    by_category: dict
    duplicate_files: int
    duplicate_wasted_bytes: int


class DeleteRequest(BaseModel):
    file_ids: list[int]


class Recommendation(BaseModel):
    type: str
    title: str
    detail: str
    file_ids: list[int]
    bytes_recoverable: int
    folder_paths: Optional[list[str]] = None


# --- Phase 3: two-stage scan architecture ---

class QuickScanRequest(BaseModel):
    path: str


class JobHandle(BaseModel):
    job_id: str


class JobStatus(BaseModel):
    id: str
    job_type: str
    status: str  # pending, running, completed, error
    root_path: Optional[str]
    categories: list[str]
    total_items: int
    completed_items: int
    current_task: Optional[str]
    percent: Optional[float]
    eta_seconds: Optional[float]
    started_at: datetime
    finished_at: Optional[datetime]
    error: Optional[str]
    result: Optional[dict]


class CategoryStat(BaseModel):
    category: str
    file_count: int
    total_bytes: int
    estimated_seconds: float
    supports_deep_analysis: bool


class CategoryStatsResponse(BaseModel):
    root_path: Optional[str]
    total_files: int
    total_bytes: int
    categories: list[CategoryStat]


class DeepScanRequest(BaseModel):
    categories: list[str]


# --- Phase 3 (legacy real-time monitor / search / chat / scheduler) ---

class MonitorStartRequest(BaseModel):
    path: str
    auto_organize: bool = False


class MonitorStatus(BaseModel):
    status: str
    root: Optional[str]
    last_event_at: Optional[float]
    events_processed: int
    error: Optional[str]
    auto_organize: bool = False
    auto_organized_count: int = 0


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    interpreted_as: str
    filters: dict
    results: list[FileOut]


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    file_ids: list[int]


class ScheduleJobRequest(BaseModel):
    job_name: str
    frequency: str  # daily, weekly, monthly
    auto_clean_duplicates: bool = False


class ScheduledJobOut(BaseModel):
    job_name: str
    frequency: str
    auto_clean_duplicates: bool


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    action: str
    detail: Optional[str]

    class Config:
        from_attributes = True


# --- Direct file management / safe delete ---

class OpenRequest(BaseModel):
    file_id: int


class RenameRequest(BaseModel):
    file_id: int
    new_name: str


class MoveRequest(BaseModel):
    file_id: int
    destination_folder: str


class CopyRequest(BaseModel):
    file_id: int
    destination_folder: str


class FileOpResult(BaseModel):
    ok: bool
    file: Optional[FileOut] = None
    error: Optional[str] = None


class TrashRequest(BaseModel):
    file_ids: list[int]


class TrashItemOut(BaseModel):
    id: int
    original_path: str
    trash_path: str
    file_name: str
    extension: Optional[str] = None
    category: Optional[str] = None
    size_bytes: int
    deleted_at: datetime
    original_file_id: Optional[int] = None

    class Config:
        from_attributes = True


class TrashActionResult(BaseModel):
    deleted: list[int] = []
    restored: list[int] = []
    purged: list[int] = []
    failed: list[dict] = []


class EmptyFolder(BaseModel):
    path: str
    size_bytes: int = 0


class ZipBackupPair(BaseModel):
    archive_id: int
    archive_name: str
    archive_path: str
    archive_bytes: int
    folder_path: str
    folder_bytes: int


# --- Collections ---

class CollectionCreateRequest(BaseModel):
    name: str


class CollectionRenameRequest(BaseModel):
    name: str


class CollectionFilesRequest(BaseModel):
    file_ids: list[int]


class CollectionOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    file_count: int
    total_bytes: int


# --- Organizer ---

class OrganizeMode(BaseModel):
    root: str
    mode: str = "category"  # category | merge_by_type | separate_files_folders
    include_hidden: bool = False


class PlannedMove(BaseModel):
    current_path: str
    new_path: str
    category: str
    size_bytes: int = 0
    is_folder: bool = False


class OrganizePreview(BaseModel):
    root: str
    mode: str
    moves: list[PlannedMove]
    folders_to_create: list[str]
    total_files: int


class OrganizeRunResult(BaseModel):
    batch_id: str
    moved: int
    folders_created: int
    failed: list[dict] = []


class UndoRequest(BaseModel):
    batch_id: Optional[str] = None  # if omitted, undo the most recent batch


class UndoResult(BaseModel):
    batch_id: str
    restored: int
    failed: list[dict] = []


class OrganizeBatchOut(BaseModel):
    id: str
    batch_type: str
    root_path: str
    files_moved: int
    folders_created: int
    duplicates_removed: int
    bytes_saved: int
    created_at: datetime
    undone: bool
    undone_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizeStats(BaseModel):
    files_moved: int
    folders_created: int
    duplicates_removed: int
    space_saved_bytes: int
    organize_runs: int
    total_files_indexed: int = 0


class DuplicateFileEntry(BaseModel):
    path: str
    size_bytes: int
    modified_at: float


class DuplicateGroupOut(BaseModel):
    sha256: str
    size_bytes: int
    keep_suggestion: str
    files: list[DuplicateFileEntry]
    wasted_bytes: int


class DuplicateScanRequest(BaseModel):
    root: str
    include_hidden: bool = False


class DuplicateDeleteRequest(BaseModel):
    file_paths: list[str]


class DuplicateDeleteResult(BaseModel):
    deleted: list[str]
    failed: list[dict] = []
    bytes_saved: int = 0


class EmptyFolderScanRequest(BaseModel):
    root: str


# --- Search index status ---

class SearchIndexStatus(BaseModel):
    indexed_files: int
    last_scan: Optional[datetime]
    status: str  # "ready" | "empty" | "scanning"


class ScheduledRunOut(BaseModel):
    id: int
    ran_at: datetime
    job_name: str
    frequency: str
    files_affected: int
    bytes_recovered: int
    detail: Optional[str]

    class Config:
        from_attributes = True
