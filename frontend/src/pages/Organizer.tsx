import { useEffect, useState } from "react";
import {
  FolderTree, FolderOpen, Loader2, Undo2, AlertTriangle, CheckCircle2,
  Copy, Trash2, FolderX, ArrowRight, FolderInput, X,
} from "lucide-react";
import {
  api, formatBytes, CATEGORY_COLORS,
  type OrganizeModeType, type OrganizePreview, type OrganizeBatchOut,
  type OrganizeStats, type DuplicateGroupOut, type EmptyFolder,
} from "../lib/api";
import StatCard from "../components/StatCard";

const MODES: { value: OrganizeModeType; label: string; blurb: string }[] = [
  { value: "category", label: "Organize by category", blurb: "Creates Organized/Images, Documents, Videos, etc. and files everything into it." },
  { value: "merge_by_type", label: "Merge files by type", blurb: "Groups loose files right where they are — Images/, Documents/, in the same folder." },
  { value: "separate_files_folders", label: "Separate files & folders", blurb: "Splits a messy root into Files/ and Folders/." },
];

type Stage = "idle" | "previewing" | "preview_ready" | "organizing" | "done" | "error";

export default function Organizer() {
  const [root, setRoot] = useState("");
  const [mode, setMode] = useState<OrganizeModeType>("category");
  const [includeHidden, setIncludeHidden] = useState(false);

  const [stage, setStage] = useState<Stage>("idle");
  const [preview, setPreview] = useState<OrganizePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<{ moved: number; folders_created: number } | null>(null);

  const [stats, setStats] = useState<OrganizeStats | null>(null);
  const [history, setHistory] = useState<OrganizeBatchOut[]>([]);
  const [undoing, setUndoing] = useState(false);

  // Duplicate cleanup
  const [dupGroups, setDupGroups] = useState<DuplicateGroupOut[] | null>(null);
  const [dupScanning, setDupScanning] = useState(false);
  const [dupSelected, setDupSelected] = useState<Set<string>>(new Set());
  const [dupDeleting, setDupDeleting] = useState(false);

  // Empty folders
  const [emptyFolders, setEmptyFolders] = useState<EmptyFolder[] | null>(null);
  const [emptyScanning, setEmptyScanning] = useState(false);
  const [emptyCleaning, setEmptyCleaning] = useState(false);

  function refreshDashboard() {
    api.organizationStats().then(setStats).catch(() => {});
    api.organizationHistory(10).then(setHistory).catch(() => {});
  }

  useEffect(refreshDashboard, []);

  async function scanDrive() {
    if (!root) return;
    setStage("previewing");
    setError(null);
    setPreview(null);
    setLastResult(null);
    try {
      const p = await api.previewOrganize(root, mode, includeHidden);
      setPreview(p);
      setStage("preview_ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
      setStage("error");
    }
  }

  async function organizeNow() {
    if (!root) return;
    setStage("organizing");
    setError(null);
    try {
      const result = await api.runOrganize(root, mode, includeHidden);
      setLastResult({ moved: result.moved, folders_created: result.folders_created });
      setPreview(null);
      setStage("done");
      refreshDashboard();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Organize failed");
      setStage("error");
    }
  }

  async function undoLast() {
    setUndoing(true);
    setError(null);
    try {
      await api.undoOrganize();
      refreshDashboard();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nothing to undo");
    } finally {
      setUndoing(false);
    }
  }

  async function scanDuplicates() {
    if (!root) return;
    setDupScanning(true);
    setDupGroups(null);
    setDupSelected(new Set());
    try {
      const groups = await api.scanOrganizeDuplicates(root, includeHidden);
      setDupGroups(groups);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Duplicate scan failed");
    } finally {
      setDupScanning(false);
    }
  }

  function toggleDup(path: string) {
    setDupSelected((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }

  async function deleteSelectedDuplicates() {
    if (dupSelected.size === 0) return;
    setDupDeleting(true);
    try {
      await api.deleteOrganizeDuplicates(Array.from(dupSelected));
      await scanDuplicates();
      refreshDashboard();
    } finally {
      setDupDeleting(false);
    }
  }

  async function scanEmpty() {
    if (!root) return;
    setEmptyScanning(true);
    setEmptyFolders(null);
    try {
      setEmptyFolders(await api.scanOrganizeEmptyFolders(root));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Empty folder scan failed");
    } finally {
      setEmptyScanning(false);
    }
  }

  async function cleanEmpty() {
    if (!emptyFolders || emptyFolders.length === 0) return;
    setEmptyCleaning(true);
    try {
      await api.cleanOrganizeEmptyFolders(emptyFolders.map((f) => f.path));
      setEmptyFolders([]);
    } finally {
      setEmptyCleaning(false);
    }
  }

  const busy = stage === "previewing" || stage === "organizing";

  return (
    <div className="flex flex-col gap-6 max-w-5xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Organize Files</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Real moves on disk via shutil.move — changes show up in Explorer immediately. Every run is logged so
          it can be undone.
        </p>
      </div>

      {/* Dashboard metrics */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard label="Total files indexed" value={stats?.total_files_indexed ?? 0} />
        <StatCard label="Files moved" value={stats?.files_moved ?? 0} accent="var(--blue)" />
        <StatCard label="Folders created" value={stats?.folders_created ?? 0} accent="var(--purple)" />
        <StatCard label="Duplicates removed" value={stats?.duplicates_removed ?? 0} accent="var(--danger)" />
        <StatCard label="Space saved" value={formatBytes(stats?.space_saved_bytes ?? 0)} accent="var(--sage)" />
      </div>

      {/* Root + mode selection */}
      <div className="glass-card p-4 flex flex-col gap-3" style={{ borderRadius: "var(--radius-md)" }}>
        <div className="flex items-center gap-3">
          <FolderInput size={15} style={{ color: "var(--text-dim)" }} className="shrink-0" />
          <input
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            placeholder="Folder to organize, e.g. C:\Users\you\Downloads"
            disabled={busy}
            className="mono flex-1 bg-transparent text-sm px-3 py-2 rounded-md border outline-none disabled:opacity-50"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          />
          <label className="flex items-center gap-1.5 text-xs shrink-0" style={{ color: "var(--text-dim)" }}>
            <input type="checkbox" checked={includeHidden} onChange={(e) => setIncludeHidden(e.target.checked)} />
            Include hidden files
          </label>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => { setMode(m.value); setPreview(null); setStage("idle"); }}
              disabled={busy}
              className="text-left rounded-lg px-3 py-2.5 border transition-colors disabled:opacity-50"
              style={{
                borderColor: mode === m.value ? "var(--panel-border-strong)" : "var(--panel-border)",
                background: mode === m.value ? "linear-gradient(135deg, rgba(124,58,237,0.16), rgba(168,85,247,0.06))" : "transparent",
              }}
            >
              <div className="text-[13px] font-medium">{m.label}</div>
              <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>{m.blurb}</div>
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={scanDrive}
            disabled={busy || !root}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-medium disabled:opacity-50"
            style={{ backgroundColor: "var(--blue)", color: "#0B0D0F" }}
          >
            {stage === "previewing" ? <Loader2 size={13} className="animate-spin" /> : <FolderTree size={13} />}
            Scan Drive
          </button>
          <button
            onClick={scanDrive}
            disabled={busy || !root}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-medium disabled:opacity-50 border"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          >
            Preview Organization
          </button>
          <button
            onClick={organizeNow}
            disabled={busy || !preview || preview.moves.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-medium disabled:opacity-50"
            style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
          >
            {stage === "organizing" ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
            Organize Now
          </button>
          <button
            onClick={undoLast}
            disabled={undoing}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-md text-xs font-medium disabled:opacity-50 border"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          >
            {undoing ? <Loader2 size={13} className="animate-spin" /> : <Undo2 size={13} />}
            Undo Last Action
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm rounded-md px-3 py-2" style={{ backgroundColor: "rgba(180,91,91,0.12)", color: "var(--danger)" }}>
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {lastResult && stage === "done" && (
        <div className="flex items-center gap-2 text-sm rounded-md px-3 py-2" style={{ backgroundColor: "rgba(52,211,153,0.10)", color: "var(--sage)" }}>
          <CheckCircle2 size={14} />
          Moved {lastResult.moved} file{lastResult.moved !== 1 ? "s" : ""}, created {lastResult.folders_created} folder{lastResult.folders_created !== 1 ? "s" : ""}. Check Explorer — it's already there.
        </div>
      )}

      {/* Preview table — Approve / Cancel */}
      {preview && stage === "preview_ready" && (
        <div className="glass-card p-4 flex flex-col gap-3" style={{ borderRadius: "var(--radius-md)" }}>
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">
              {preview.total_files} file{preview.total_files !== 1 ? "s" : ""} will move · {preview.folders_to_create.length} folder{preview.folders_to_create.length !== 1 ? "s" : ""} will be created
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setPreview(null); setStage("idle"); }}
                className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs border"
                style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
              >
                <X size={12} /> Cancel
              </button>
              <button
                onClick={organizeNow}
                className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-medium"
                style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
              >
                <CheckCircle2 size={12} /> Approve & Organize
              </button>
            </div>
          </div>

          {preview.moves.length === 0 ? (
            <div className="text-xs py-6 text-center" style={{ color: "var(--text-dim)" }}>
              Nothing to move — this folder is already organized for this mode.
            </div>
          ) : (
            <div className="max-h-80 overflow-y-auto rounded-lg border" style={{ borderColor: "var(--panel-border)" }}>
              <table className="w-full text-xs">
                <thead className="sticky top-0" style={{ backgroundColor: "var(--panel-solid)" }}>
                  <tr style={{ color: "var(--text-dim)" }}>
                    <th className="text-left font-medium px-3 py-2">Current path</th>
                    <th className="text-left font-medium px-3 py-2 w-8"></th>
                    <th className="text-left font-medium px-3 py-2">New path</th>
                    <th className="text-left font-medium px-3 py-2">Category</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.moves.map((m) => (
                    <tr key={m.current_path} className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                      <td className="mono px-3 py-1.5 truncate max-w-[220px]" style={{ color: "var(--text-dim)" }}>{m.current_path}</td>
                      <td className="px-3 py-1.5"><ArrowRight size={11} style={{ color: "var(--text-faint)" }} /></td>
                      <td className="mono px-3 py-1.5 truncate max-w-[260px]">{m.new_path}</td>
                      <td className="px-3 py-1.5">
                        <span
                          className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                          style={{ backgroundColor: `${CATEGORY_COLORS[m.category] ?? "#6B6B6B"}22`, color: CATEGORY_COLORS[m.category] ?? "#6B6B6B" }}
                        >
                          {m.category}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Duplicate cleanup */}
      <div className="glass-card p-4 flex flex-col gap-3" style={{ borderRadius: "var(--radius-md)" }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium flex items-center gap-1.5"><Copy size={14} /> Smart Duplicate Cleanup</div>
            <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>SHA256-based. Nothing is deleted until you confirm specific files below.</div>
          </div>
          <button
            onClick={scanDuplicates}
            disabled={dupScanning || !root}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50 border"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          >
            {dupScanning ? <Loader2 size={12} className="animate-spin" /> : <Copy size={12} />}
            Scan for duplicates
          </button>
        </div>

        {dupGroups && dupGroups.length === 0 && (
          <div className="text-xs py-3 text-center" style={{ color: "var(--text-dim)" }}>No duplicates found.</div>
        )}

        {dupGroups && dupGroups.length > 0 && (
          <>
            <div className="flex flex-col gap-2 max-h-72 overflow-y-auto">
              {dupGroups.map((g) => (
                <div key={g.sha256} className="rounded-lg border p-2.5" style={{ borderColor: "var(--panel-border)" }}>
                  <div className="text-[11px] mb-1.5" style={{ color: "var(--text-dim)" }}>
                    {g.files.length} copies · {formatBytes(g.size_bytes)} each · {formatBytes(g.wasted_bytes)} wasted
                  </div>
                  {g.files.map((f) => (
                    <label key={f.path} className="flex items-center gap-2 text-xs py-0.5 mono">
                      <input
                        type="checkbox"
                        checked={dupSelected.has(f.path)}
                        disabled={f.path === g.keep_suggestion}
                        onChange={() => toggleDup(f.path)}
                      />
                      <span className={f.path === g.keep_suggestion ? "" : ""} style={{ color: f.path === g.keep_suggestion ? "var(--sage)" : "var(--text)" }}>
                        {f.path} {f.path === g.keep_suggestion && "(keep — newest)"}
                      </span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
            <button
              onClick={deleteSelectedDuplicates}
              disabled={dupSelected.size === 0 || dupDeleting}
              className="self-start flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
              style={{ backgroundColor: "var(--danger)", color: "#fff" }}
            >
              {dupDeleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
              Delete {dupSelected.size || ""} confirmed duplicate{dupSelected.size !== 1 ? "s" : ""}
            </button>
          </>
        )}
      </div>

      {/* Empty folder cleanup */}
      <div className="glass-card p-4 flex flex-col gap-3" style={{ borderRadius: "var(--radius-md)" }}>
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium flex items-center gap-1.5"><FolderX size={14} /> Empty Folder Cleanup</div>
            <div className="text-[11px] mt-0.5" style={{ color: "var(--text-dim)" }}>Detects folders left behind after organizing. Skips system folders.</div>
          </div>
          <button
            onClick={scanEmpty}
            disabled={emptyScanning || !root}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50 border"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          >
            {emptyScanning ? <Loader2 size={12} className="animate-spin" /> : <FolderOpen size={12} />}
            Clean Empty Folders
          </button>
        </div>

        {emptyFolders && emptyFolders.length === 0 && (
          <div className="text-xs py-3 text-center" style={{ color: "var(--text-dim)" }}>No empty folders found.</div>
        )}

        {emptyFolders && emptyFolders.length > 0 && (
          <>
            <div className="max-h-48 overflow-y-auto flex flex-col gap-1">
              {emptyFolders.map((f) => (
                <div key={f.path} className="mono text-xs px-2 py-1 rounded" style={{ color: "var(--text-dim)", backgroundColor: "rgba(148,163,184,0.06)" }}>
                  {f.path}
                </div>
              ))}
            </div>
            <button
              onClick={cleanEmpty}
              disabled={emptyCleaning}
              className="self-start flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
              style={{ backgroundColor: "var(--clay)", color: "#0B0D0F" }}
            >
              {emptyCleaning ? <Loader2 size={12} className="animate-spin" /> : <FolderX size={12} />}
              Remove {emptyFolders.length} empty folder{emptyFolders.length !== 1 ? "s" : ""}
            </button>
          </>
        )}
      </div>

      {/* History */}
      {history.length > 0 && (
        <div className="glass-card p-4 flex flex-col gap-2" style={{ borderRadius: "var(--radius-md)" }}>
          <div className="text-sm font-medium">Organization history</div>
          <div className="flex flex-col gap-1">
            {history.map((b) => (
              <div key={b.id} className="flex items-center justify-between text-xs py-1.5 border-t" style={{ borderColor: "var(--panel-border)" }}>
                <div className="flex items-center gap-2">
                  <span className="mono" style={{ color: "var(--text-dim)" }}>{new Date(b.created_at).toLocaleString()}</span>
                  <span>{b.batch_type.replace(/_/g, " ")}</span>
                  <span className="mono truncate max-w-[220px]" style={{ color: "var(--text-faint)" }}>{b.root_path}</span>
                </div>
                <div className="flex items-center gap-3" style={{ color: "var(--text-dim)" }}>
                  <span>{b.files_moved} moved</span>
                  {b.undone && <span style={{ color: "var(--clay)" }}>undone</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
