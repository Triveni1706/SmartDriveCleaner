import { useEffect, useState } from "react";
import { Sparkles, Trash2, Loader2, FolderX } from "lucide-react";
import { api, formatBytes, type Recommendation } from "../lib/api";

const ICON_COLOR: Record<string, string> = {
  duplicates: "var(--clay)",
  similar_images: "var(--purple)",
  blurry_images: "var(--danger)",
  old_files: "var(--blue)",
  unused_1_year: "var(--blue)",
  unclassified_pdfs: "var(--text-dim)",
  empty_folders: "var(--text-dim)",
  zip_backups: "var(--clay)",
};

// Types that are "review only" — informational, no one-click apply.
const REVIEW_ONLY_PREFIXES = ["large_files_", "old_files", "unused_1_year", "unclassified_pdfs"];

function isReviewOnly(type: string): boolean {
  return REVIEW_ONLY_PREFIXES.some((p) => type.startsWith(p));
}

export default function Recommendations() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api
      .recommendations()
      .then(setRecs)
      .catch(() => setRecs([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function apply(rec: Recommendation) {
    setApplying(rec.type);
    try {
      if (rec.type === "empty_folders") {
        if (rec.folder_paths && rec.folder_paths.length > 0) {
          await api.deleteEmptyFolders(rec.folder_paths);
        }
      } else if (rec.file_ids.length > 0) {
        // Safe delete: moves to Trash, recoverable from the Trash page.
        await api.trashFiles(rec.file_ids);
      }
      load();
    } finally {
      setApplying(null);
    }
  }

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Recommendations</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Rule-based suggestions from your scan data — each one is fully explainable, not a black-box model.
        </p>
      </div>

      {!loading && recs.length === 0 && (
        <div
          className="rounded-lg border border-dashed p-10 text-center text-sm"
          style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
        >
          Nothing to recommend yet — run a scan, or your drive is already clean.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {recs.map((rec) => (
          <div
            key={rec.type}
            className="rounded-lg border p-4 flex items-start gap-3"
            style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
          >
            {rec.type === "empty_folders" ? (
              <FolderX size={16} className="mt-0.5 shrink-0" style={{ color: ICON_COLOR[rec.type] || "var(--sage)" }} />
            ) : (
              <Sparkles size={16} className="mt-0.5 shrink-0" style={{ color: ICON_COLOR[rec.type] || "var(--sage)" }} />
            )}
            <div className="flex-1">
              <div className="text-sm font-medium">{rec.title}</div>
              <div className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>
                {rec.detail}
              </div>
            </div>
            {!isReviewOnly(rec.type) &&
              (rec.file_ids.length > 0 || (rec.folder_paths && rec.folder_paths.length > 0)) && (
                <button
                  onClick={() => apply(rec)}
                  disabled={applying === rec.type}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium shrink-0 disabled:opacity-50"
                  style={{ backgroundColor: "var(--danger)", color: "#fff" }}
                >
                  {applying === rec.type ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                  {rec.type === "empty_folders" ? "Delete folders" : "Move to trash"}
                </button>
              )}
          </div>
        ))}
      </div>

      {recs.some((r) => r.bytes_recoverable > 0) && (
        <div className="text-xs mono mt-2" style={{ color: "var(--text-dim)" }}>
          Total recoverable across all recommendations:{" "}
          <span style={{ color: "var(--sage)" }}>
            {formatBytes(recs.reduce((sum, r) => sum + r.bytes_recoverable, 0))}
          </span>
        </div>
      )}
    </div>
  );
}
