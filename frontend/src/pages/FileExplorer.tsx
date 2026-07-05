import { useEffect, useState } from "react";
import {
  FolderOpen, ExternalLink, Pencil, FolderInput, Copy, Trash2,
  FolderPlus, Loader2, X, Check,
} from "lucide-react";
import { api, formatBytes, CATEGORY_COLORS, type ScannedFile, type CollectionOut } from "../lib/api";

const CATEGORIES = ["All", "Documents", "Images", "PDFs", "Archives", "Videos", "Audio", "Others"];

type RowAction = "rename" | "move" | "copy" | null;

export default function FileExplorer() {
  const [files, setFiles] = useState<ScannedFile[]>([]);
  const [category, setCategory] = useState("All");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busyId, setBusyId] = useState<number | null>(null);
  const [rowAction, setRowAction] = useState<{ id: number; action: RowAction } | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [collections, setCollections] = useState<CollectionOut[]>([]);
  const [collectionPickerFor, setCollectionPickerFor] = useState<number[] | null>(null);
  const [newCollectionName, setNewCollectionName] = useState("");

  function load() {
    setLoading(true);
    api
      .files(category === "All" ? undefined : category)
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [category]);
  useEffect(() => {
    api.listCollections().then(setCollections).catch(() => setCollections([]));
  }, []);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) => (prev.size === files.length ? new Set() : new Set(files.map((f) => f.id))));
  }

  async function runOp<T>(id: number, op: () => Promise<T>) {
    setBusyId(id);
    setError(null);
    try {
      await op();
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operation failed");
    } finally {
      setBusyId(null);
    }
  }

  function startRowAction(f: ScannedFile, action: RowAction) {
    setRowAction({ id: f.id, action });
    setInputValue(action === "rename" ? f.name : "");
    setError(null);
  }

  async function confirmRowAction() {
    if (!rowAction) return;
    const { id, action } = rowAction;
    setRowAction(null);
    if (action === "rename" && inputValue.trim()) {
      await runOp(id, () => api.renameFile(id, inputValue.trim()));
    } else if (action === "move" && inputValue.trim()) {
      await runOp(id, () => api.moveFile(id, inputValue.trim()));
    } else if (action === "copy" && inputValue.trim()) {
      await runOp(id, () => api.copyFile(id, inputValue.trim()));
    }
  }

  async function trashSelected() {
    if (selected.size === 0) return;
    setBusyId(-1);
    try {
      await api.trashFiles(Array.from(selected));
      setSelected(new Set());
      load();
    } finally {
      setBusyId(null);
    }
  }

  async function addSelectedToCollection(collectionId: number) {
    const ids = collectionPickerFor ?? Array.from(selected);
    if (ids.length === 0) return;
    await api.addFilesToCollection(collectionId, ids);
    setCollectionPickerFor(null);
    setSelected(new Set());
  }

  async function createAndAddToCollection() {
    if (!newCollectionName.trim()) return;
    const c = await api.createCollection(newCollectionName.trim());
    setCollections((prev) => [...prev, c]);
    setNewCollectionName("");
    await addSelectedToCollection(c.id);
  }

  const selectedBytes = files.filter((f) => selected.has(f.id)).reduce((sum, f) => sum + f.size_bytes, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">File Explorer</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
            {files.length} file{files.length !== 1 ? "s" : ""}, oldest first. Open, rename, move, copy, or organize
            files directly — no need for the OS file manager.
          </p>
        </div>
        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs mono" style={{ color: "var(--text-dim)" }}>
              {selected.size} selected · {formatBytes(selectedBytes)}
            </span>
            <button
              onClick={() => setCollectionPickerFor(Array.from(selected))}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium"
              style={{ backgroundColor: "var(--panel)", color: "var(--text)", border: "1px solid var(--panel-border)" }}
            >
              <FolderPlus size={12} />
              Add to collection
            </button>
            <button
              onClick={trashSelected}
              disabled={busyId === -1}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
              style={{ backgroundColor: "var(--danger)", color: "#fff" }}
            >
              {busyId === -1 ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
              Move to trash
            </button>
          </div>
        )}
      </div>

      {error && (
        <div
          className="rounded-md px-3 py-2 text-xs"
          style={{ backgroundColor: "rgba(180,91,91,0.12)", color: "var(--danger)" }}
        >
          {error}
        </div>
      )}

      <div className="flex gap-1.5 flex-wrap">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setCategory(c)}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={{
              backgroundColor: category === c ? "var(--panel)" : "transparent",
              color: category === c ? "var(--text)" : "var(--text-dim)",
              border: `1px solid ${category === c ? "var(--panel-border)" : "transparent"}`,
            }}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--panel)" }} className="text-left">
              <th className="px-3 py-2.5 w-8">
                <input
                  type="checkbox"
                  className="accent-[var(--sage)]"
                  checked={files.length > 0 && selected.size === files.length}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Name</th>
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Category</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Size</th>
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Modified</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {!loading && files.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
                  No files. Run a scan from the Overview page.
                </td>
              </tr>
            )}
            {files.map((f) => (
              <tr key={f.id} className="border-t align-top" style={{ borderColor: "var(--panel-border)" }}>
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    className="accent-[var(--sage)]"
                    checked={selected.has(f.id)}
                    onChange={() => toggle(f.id)}
                  />
                </td>
                <td className="px-4 py-2.5 max-w-xs">
                  {rowAction?.id === f.id ? (
                    <div className="flex items-center gap-1.5">
                      <input
                        autoFocus
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && confirmRowAction()}
                        placeholder={
                          rowAction.action === "rename" ? "New file name" : "Destination folder path"
                        }
                        className="px-2 py-1 rounded text-xs w-56"
                        style={{ backgroundColor: "var(--bg)", border: "1px solid var(--panel-border)", color: "var(--text)" }}
                      />
                      <button onClick={confirmRowAction} style={{ color: "var(--sage)" }}>
                        <Check size={14} />
                      </button>
                      <button onClick={() => setRowAction(null)} style={{ color: "var(--text-dim)" }}>
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    <span className="truncate block" title={f.path}>
                      {f.name}
                      {f.is_duplicate && (
                        <span
                          className="ml-2 text-[10px] px-1.5 py-0.5 rounded mono"
                          style={{ backgroundColor: "rgba(193,122,78,0.15)", color: "var(--clay)" }}
                        >
                          dup
                        </span>
                      )}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5">
                  <span className="flex items-center gap-1.5 text-xs">
                    <span
                      className="w-1.5 h-1.5 rounded-sm"
                      style={{ backgroundColor: CATEGORY_COLORS[f.category] || "#555" }}
                    />
                    {f.category}
                  </span>
                </td>
                <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                  {formatBytes(f.size_bytes)}
                </td>
                <td className="px-4 py-2.5 mono text-xs" style={{ color: "var(--text-dim)" }}>
                  {f.modified_at ? new Date(f.modified_at).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    {busyId === f.id ? (
                      <Loader2 size={13} className="animate-spin" style={{ color: "var(--text-dim)" }} />
                    ) : (
                      <>
                        <IconBtn title="Open file" onClick={() => runOp(f.id, () => api.openFile(f.id))}>
                          <ExternalLink size={13} />
                        </IconBtn>
                        <IconBtn title="Open containing folder" onClick={() => runOp(f.id, () => api.openFolder(f.id))}>
                          <FolderOpen size={13} />
                        </IconBtn>
                        <IconBtn title="Rename" onClick={() => startRowAction(f, "rename")}>
                          <Pencil size={13} />
                        </IconBtn>
                        <IconBtn title="Move" onClick={() => startRowAction(f, "move")}>
                          <FolderInput size={13} />
                        </IconBtn>
                        <IconBtn title="Copy" onClick={() => startRowAction(f, "copy")}>
                          <Copy size={13} />
                        </IconBtn>
                        <IconBtn title="Add to collection" onClick={() => setCollectionPickerFor([f.id])}>
                          <FolderPlus size={13} />
                        </IconBtn>
                        <IconBtn
                          title="Move to trash"
                          danger
                          onClick={() => runOp(f.id, () => api.trashFiles([f.id]))}
                        >
                          <Trash2 size={13} />
                        </IconBtn>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {collectionPickerFor && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
          onClick={() => setCollectionPickerFor(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-lg border p-4 w-80 flex flex-col gap-3"
            style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
          >
            <div className="text-sm font-medium">
              Add {collectionPickerFor.length} file{collectionPickerFor.length !== 1 ? "s" : ""} to collection
            </div>
            <div className="flex flex-col gap-1 max-h-48 overflow-y-auto">
              {collections.length === 0 && (
                <div className="text-xs" style={{ color: "var(--text-dim)" }}>No collections yet — create one below.</div>
              )}
              {collections.map((c) => (
                <button
                  key={c.id}
                  onClick={() => addSelectedToCollection(c.id)}
                  className="text-left px-2.5 py-1.5 rounded text-sm hover:bg-[var(--bg)]"
                  style={{ border: "1px solid var(--panel-border)" }}
                >
                  {c.name}
                  <span className="text-xs ml-2" style={{ color: "var(--text-dim)" }}>
                    {c.file_count} files
                  </span>
                </button>
              ))}
            </div>
            <div className="flex items-center gap-1.5 pt-2 border-t" style={{ borderColor: "var(--panel-border)" }}>
              <input
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createAndAddToCollection()}
                placeholder="New collection name"
                className="flex-1 px-2 py-1.5 rounded text-xs"
                style={{ backgroundColor: "var(--bg)", border: "1px solid var(--panel-border)", color: "var(--text)" }}
              />
              <button
                onClick={createAndAddToCollection}
                className="px-2.5 py-1.5 rounded text-xs font-medium"
                style={{ backgroundColor: "var(--sage)", color: "#fff" }}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function IconBtn({
  children, onClick, title, danger,
}: { children: React.ReactNode; onClick: () => void; title: string; danger?: boolean }) {
  return (
    <button
      title={title}
      onClick={onClick}
      className="p-1.5 rounded-md transition-colors hover:bg-[var(--bg)]"
      style={{ color: danger ? "var(--danger)" : "var(--text-dim)" }}
    >
      {children}
    </button>
  );
}
