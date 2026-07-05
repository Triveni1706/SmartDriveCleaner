const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8811/api";

export interface ScannedFile {
  id: number;
  name: string;
  path: string;
  extension: string;
  category: string;
  size_bytes: number;
  created_at: string | null;
  modified_at: string | null;
  accessed_at: string | null;
  sha256: string;
  is_duplicate: boolean;
  duplicate_group: string | null;
  subcategory: string | null;
  subcategory_confidence: number | null;
  is_blurry: boolean | null;
  blur_score: number | null;
  pdf_page_count: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  image_width: number | null;
  image_height: number | null;
  archive_file_count: number | null;
  archive_uncompressed_bytes: number | null;
  perceptual_hash: string | null;
  similar_group: string | null;
}

export interface ScanResult {
  scanned_files: number;
  total_bytes: number;
  duplicate_groups: number;
  duplicate_wasted_bytes: number;
  similar_image_groups: number;
}

export interface StorageStats {
  total_files: number;
  total_bytes: number;
  by_category: Record<string, { count: number; bytes: number }>;
  duplicate_files: number;
  duplicate_wasted_bytes: number;
}

export interface Recommendation {
  type: string;
  title: string;
  detail: string;
  file_ids: number[];
  bytes_recoverable: number;
  folder_paths?: string[] | null;
}

export interface TrashItemOut {
  id: number;
  original_path: string;
  trash_path: string;
  file_name: string;
  extension: string | null;
  category: string | null;
  size_bytes: number;
  deleted_at: string;
  original_file_id: number | null;
}

export interface TrashActionResult {
  deleted: number[];
  restored: number[];
  purged: number[];
  failed: { id: number; error: string }[];
}

export interface EmptyFolder {
  path: string;
  size_bytes: number;
}

export interface ZipBackupPair {
  archive_id: number;
  archive_name: string;
  archive_path: string;
  archive_bytes: number;
  folder_path: string;
  folder_bytes: number;
}

export interface CollectionOut {
  id: number;
  name: string;
  created_at: string;
  file_count: number;
  total_bytes: number;
}

export interface SearchIndexStatus {
  indexed_files: number;
  last_scan: string | null;
  status: "ready" | "empty" | "scanning";
}

export interface MonitorStatus {
  status: "stopped" | "watching" | "error";
  root: string | null;
  last_event_at: number | null;
  events_processed: number;
  error: string | null;
  auto_organize: boolean;
  auto_organized_count: number;
}

// --- Organizer ---

export type OrganizeModeType = "category" | "merge_by_type" | "separate_files_folders";

export interface PlannedMove {
  current_path: string;
  new_path: string;
  category: string;
  size_bytes: number;
  is_folder: boolean;
}

export interface OrganizePreview {
  root: string;
  mode: string;
  moves: PlannedMove[];
  folders_to_create: string[];
  total_files: number;
}

export interface OrganizeRunResult {
  batch_id: string;
  moved: number;
  folders_created: number;
  failed: { path: string; error: string }[];
}

export interface UndoResult {
  batch_id: string;
  restored: number;
  failed: { path: string; error: string }[];
}

export interface OrganizeBatchOut {
  id: string;
  batch_type: string;
  root_path: string;
  files_moved: number;
  folders_created: number;
  duplicates_removed: number;
  bytes_saved: number;
  created_at: string;
  undone: boolean;
  undone_at: string | null;
}

export interface OrganizeStats {
  files_moved: number;
  folders_created: number;
  duplicates_removed: number;
  space_saved_bytes: number;
  organize_runs: number;
  total_files_indexed: number;
}

export interface DuplicateFileEntry {
  path: string;
  size_bytes: number;
  modified_at: number;
}

export interface DuplicateGroupOut {
  sha256: string;
  size_bytes: number;
  keep_suggestion: string;
  files: DuplicateFileEntry[];
  wasted_bytes: number;
}

export interface DuplicateDeleteResult {
  deleted: string[];
  failed: { path: string; error: string }[];
  bytes_saved: number;
}

export interface SearchResponse {
  interpreted_as: string;
  filters: Record<string, unknown>;
  results: ScannedFile[];
}

export interface ChatResponse {
  reply: string;
  file_ids: number[];
}

export interface ScheduledJob {
  job_name: string;
  frequency: "daily" | "weekly" | "monthly";
  auto_clean_duplicates: boolean;
}

export interface ScheduledRun {
  id: number;
  ran_at: string;
  job_name: string;
  frequency: string;
  files_affected: number;
  bytes_recovered: number;
  detail: string | null;
}

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  action: string;
  detail: string | null;
}

// --- Two-stage scan architecture ---

export interface JobHandle {
  job_id: string;
}

export interface JobStatus {
  id: string;
  job_type: "quick_scan" | "deep_scan";
  status: "pending" | "running" | "completed" | "error";
  root_path: string | null;
  categories: string[];
  total_items: number;
  completed_items: number;
  current_task: string | null;
  percent: number | null;
  eta_seconds: number | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  result: Record<string, any> | null;
}

export interface CategoryStat {
  category: string;
  file_count: number;
  total_bytes: number;
  estimated_seconds: number;
  supports_deep_analysis: boolean;
}

export interface CategoryStatsResponse {
  root_path: string | null;
  total_files: number;
  total_bytes: number;
  categories: CategoryStat[];
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  scan: (path: string) =>
    request<ScanResult>("/scan", { method: "POST", body: JSON.stringify({ path }) }),
  files: (category?: string) =>
    request<ScannedFile[]>(`/files${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  duplicates: () => request<ScannedFile[]>("/duplicates"),
  similarImages: () => request<ScannedFile[]>("/similar-images"),
  blurryImages: () => request<ScannedFile[]>("/blurry-images"),
  pdfs: (subcategory?: string) =>
    request<ScannedFile[]>(`/pdfs${subcategory ? `?subcategory=${encodeURIComponent(subcategory)}` : ""}`),
  archives: () => request<ScannedFile[]>("/archives"),
  recommendations: () => request<Recommendation[]>("/recommendations"),
  stats: () => request<StorageStats>("/stats"),
  deleteFiles: (file_ids: number[]) =>
    request<{ deleted: number[]; failed: { id: number; error: string }[] }>("/files", {
      method: "DELETE",
      body: JSON.stringify({ file_ids }),
    }),

  // --- Phase 3 ---
  monitorStart: (path: string, auto_organize = false) =>
    request<MonitorStatus>("/monitor/start", { method: "POST", body: JSON.stringify({ path, auto_organize }) }),
  monitorStop: () => request<MonitorStatus>("/monitor/stop", { method: "POST" }),
  monitorStatus: () => request<MonitorStatus>("/monitor/status"),

  search: (query: string) =>
    request<SearchResponse>("/search", { method: "POST", body: JSON.stringify({ query }) }),

  chat: (message: string) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify({ message }) }),

  scheduleJob: (job_name: string, frequency: string, auto_clean_duplicates: boolean) =>
    request<ScheduledJob>("/scheduler/jobs", {
      method: "POST",
      body: JSON.stringify({ job_name, frequency, auto_clean_duplicates }),
    }),
  listJobs: () => request<ScheduledJob[]>("/scheduler/jobs"),
  deleteJob: (job_name: string) => request<{ deleted: string }>(`/scheduler/jobs/${encodeURIComponent(job_name)}`, { method: "DELETE" }),
  runJobNow: (job_name: string) => request<{ ran: string }>(`/scheduler/jobs/${encodeURIComponent(job_name)}/run`, { method: "POST" }),
  listRuns: () => request<ScheduledRun[]>("/scheduler/runs"),

  generateReport: () => request<{ filepath: string; filename: string }>("/reports/generate", { method: "POST" }),
  reportDownloadUrl: (filename: string) => `${BASE_URL}/reports/${encodeURIComponent(filename)}`,

  auditLog: (limit = 100) => request<AuditLogEntry[]>(`/audit-log?limit=${limit}`),

  // --- Two-stage scan architecture ---
  quickScan: (path: string) =>
    request<JobHandle>("/quick-scan", { method: "POST", body: JSON.stringify({ path }) }),
  categoryStats: () => request<CategoryStatsResponse>("/category-stats"),
  deepScan: (categories: string[]) =>
    request<JobHandle>("/deep-scan", { method: "POST", body: JSON.stringify({ categories }) }),
  jobStatus: (jobId: string) => request<JobStatus>(`/jobs/${jobId}`),
  recommendationsFor: (categories: string[]) =>
    request<Recommendation[]>(`/recommendations?categories=${encodeURIComponent(categories.join(","))}`),

  // --- Direct file management ---
  openFile: (file_id: number) =>
    request<{ opened: string }>("/file-ops/open", { method: "POST", body: JSON.stringify({ file_id }) }),
  openFolder: (file_id: number) =>
    request<{ opened_folder_for: string }>("/file-ops/open-folder", { method: "POST", body: JSON.stringify({ file_id }) }),
  renameFile: (file_id: number, new_name: string) =>
    request<{ ok: boolean; file: ScannedFile }>("/file-ops/rename", { method: "POST", body: JSON.stringify({ file_id, new_name }) }),
  moveFile: (file_id: number, destination_folder: string) =>
    request<{ ok: boolean; file: ScannedFile }>("/file-ops/move", { method: "POST", body: JSON.stringify({ file_id, destination_folder }) }),
  copyFile: (file_id: number, destination_folder: string) =>
    request<{ ok: boolean; file: ScannedFile }>("/file-ops/copy", { method: "POST", body: JSON.stringify({ file_id, destination_folder }) }),

  // --- Safe delete / trash / recovery ---
  trashFiles: (file_ids: number[]) =>
    request<TrashActionResult>("/files/trash", { method: "POST", body: JSON.stringify({ file_ids }) }),
  listTrash: () => request<TrashItemOut[]>("/trash"),
  restoreFromTrash: (file_ids: number[]) =>
    request<TrashActionResult>("/trash/restore", { method: "POST", body: JSON.stringify({ file_ids }) }),
  purgeTrash: (file_ids: number[]) =>
    request<TrashActionResult>("/trash/permanent", { method: "DELETE", body: JSON.stringify({ file_ids }) }),
  emptyTrash: () => request<TrashActionResult>("/trash/empty", { method: "DELETE" }),

  // --- Empty folders / ZIP backups ---
  emptyFolders: () => request<EmptyFolder[]>("/empty-folders"),
  deleteEmptyFolders: (paths: string[]) =>
    request<{ deleted: string[]; failed: { path: string; error: string }[] }>("/empty-folders", {
      method: "DELETE",
      body: JSON.stringify({ paths }),
    }),
  zipBackups: () => request<ZipBackupPair[]>("/zip-backups"),

  // --- Collections ---
  listCollections: () => request<CollectionOut[]>("/collections"),
  createCollection: (name: string) =>
    request<CollectionOut>("/collections", { method: "POST", body: JSON.stringify({ name }) }),
  renameCollection: (id: number, name: string) =>
    request<CollectionOut>(`/collections/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteCollection: (id: number) =>
    request<{ deleted: number }>(`/collections/${id}`, { method: "DELETE" }),
  addFilesToCollection: (id: number, file_ids: number[]) =>
    request<{ added: number }>(`/collections/${id}/files`, { method: "POST", body: JSON.stringify({ file_ids }) }),
  removeFilesFromCollection: (id: number, file_ids: number[]) =>
    request<{ removed: number }>(`/collections/${id}/files`, { method: "DELETE", body: JSON.stringify({ file_ids }) }),
  collectionFiles: (id: number) => request<ScannedFile[]>(`/collections/${id}/files`),

  // --- Search index status ---
  searchStatus: () => request<SearchIndexStatus>("/search/status"),

  // --- Organizer ---
  previewOrganize: (root: string, mode: OrganizeModeType, include_hidden = false) =>
    request<OrganizePreview>("/preview-organize", {
      method: "POST",
      body: JSON.stringify({ root, mode, include_hidden }),
    }),
  runOrganize: (root: string, mode: OrganizeModeType, include_hidden = false) =>
    request<OrganizeRunResult>("/organize", {
      method: "POST",
      body: JSON.stringify({ root, mode, include_hidden }),
    }),
  undoOrganize: (batch_id?: string) =>
    request<UndoResult>("/undo-organize", { method: "POST", body: JSON.stringify({ batch_id }) }),
  organizationHistory: (limit = 50) =>
    request<OrganizeBatchOut[]>(`/organization-history?limit=${limit}`),
  organizationStats: () => request<OrganizeStats>("/organization-stats"),

  scanOrganizeDuplicates: (root: string, include_hidden = false) =>
    request<DuplicateGroupOut[]>("/organize/duplicates/scan", {
      method: "POST",
      body: JSON.stringify({ root, include_hidden }),
    }),
  deleteOrganizeDuplicates: (file_paths: string[]) =>
    request<DuplicateDeleteResult>("/organize/duplicates/delete", {
      method: "POST",
      body: JSON.stringify({ file_paths }),
    }),

  scanOrganizeEmptyFolders: (root: string) =>
    request<EmptyFolder[]>("/organize/empty-folders/scan", {
      method: "POST",
      body: JSON.stringify({ root }),
    }),
  cleanOrganizeEmptyFolders: (paths: string[]) =>
    request<{ deleted: string[]; failed: { path: string; error: string }[] }>("/organize/empty-folders", {
      method: "DELETE",
      body: JSON.stringify({ paths }),
    }),
};

/** Polls a job until it reaches completed/error, calling onUpdate on every
 * poll. Returns the final JobStatus. Used by the scan dashboard so the UI
 * can show current_task / percent / ETA while Stage 1 or Stage 2 runs. */
export async function pollJob(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  intervalMs = 500
): Promise<JobStatus> {
  while (true) {
    const status = await api.jobStatus(jobId);
    onUpdate(status);
    if (status.status === "completed" || status.status === "error") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export const CATEGORY_COLORS: Record<string, string> = {
  Documents: "#5B8C7B",
  Images: "#C17A4E",
  PDFs: "#7A9CC6",
  Archives: "#B45B5B",
  Videos: "#9B7BC6",
  Audio: "#C6B45B",
  Others: "#6B6B6B",
};
