import { useEffect, useState } from "react";
import { FolderPlus, Pencil, Trash2, ChevronRight, ChevronDown, X, Loader2 } from "lucide-react";
import { api, formatBytes, CATEGORY_COLORS, type CollectionOut, type ScannedFile } from "../lib/api";

export default function Collections() {
  const [collections, setCollections] = useState<CollectionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [files, setFiles] = useState<Record<number, ScannedFile[]>>({});
  const [renaming, setRenaming] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api
      .listCollections()
      .then(setCollections)
      .catch(() => setCollections([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function toggleExpand(c: CollectionOut) {
    if (expanded === c.id) {
      setExpanded(null);
      return;
    }
    setExpanded(c.id);
    if (!files[c.id]) {
      const f = await api.collectionFiles(c.id);
      setFiles((prev) => ({ ...prev, [c.id]: f }));
    }
  }

  async function create() {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      await api.createCollection(newName.trim());
      setNewName("");
      load();
    } finally {
      setBusy(false);
    }
  }

  async function rename(id: number) {
    if (!renameValue.trim()) {
      setRenaming(null);
      return;
    }
    setBusy(true);
    try {
      await api.renameCollection(id, renameValue.trim());
      setRenaming(null);
      load();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    try {
      await api.deleteCollection(id);
      if (expanded === id) setExpanded(null);
      load();
    } finally {
      setBusy(false);
    }
  }

  async function removeFile(collectionId: number, fileId: number) {
    await api.removeFilesFromCollection(collectionId, [fileId]);
    setFiles((prev) => ({ ...prev, [collectionId]: prev[collectionId].filter((f) => f.id !== fileId) }));
    load();
  }

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Collections</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Group files together — Important PDFs, Certificates, Resumes, Personal Photos, whatever makes sense to you.
          Add files from File Explorer or here.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <input
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()}
          placeholder="New collection name (e.g. Important PDFs)"
          className="flex-1 px-3 py-2 rounded-md text-sm"
          style={{ backgroundColor: "var(--panel)", border: "1px solid var(--panel-border)", color: "var(--text)" }}
        />
        <button
          onClick={create}
          disabled={busy || !newName.trim()}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-md text-sm font-medium disabled:opacity-50"
          style={{ backgroundColor: "var(--sage)", color: "#fff" }}
        >
          <FolderPlus size={14} />
          Create
        </button>
      </div>

      {!loading && collections.length === 0 && (
        <div
          className="rounded-lg border border-dashed p-10 text-center text-sm"
          style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
        >
          No collections yet.
        </div>
      )}

      <div className="flex flex-col gap-2">
        {collections.map((c) => (
          <div key={c.id} className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
            <div
              className="flex items-center gap-2 px-4 py-3 cursor-pointer"
              style={{ backgroundColor: "var(--panel)" }}
              onClick={() => toggleExpand(c)}
            >
              {expanded === c.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {renaming === c.id ? (
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && rename(c.id)}
                  onClick={(e) => e.stopPropagation()}
                  onBlur={() => rename(c.id)}
                  className="px-2 py-1 rounded text-sm flex-1"
                  style={{ backgroundColor: "var(--bg)", border: "1px solid var(--panel-border)", color: "var(--text)" }}
                />
              ) : (
                <span className="text-sm font-medium flex-1">{c.name}</span>
              )}
              <span className="text-xs mono" style={{ color: "var(--text-dim)" }}>
                {c.file_count} files · {formatBytes(c.total_bytes)}
              </span>
              <button
                title="Rename"
                onClick={(e) => {
                  e.stopPropagation();
                  setRenaming(c.id);
                  setRenameValue(c.name);
                }}
                className="p-1 rounded hover:bg-[var(--bg)]"
                style={{ color: "var(--text-dim)" }}
              >
                <Pencil size={13} />
              </button>
              <button
                title="Delete collection"
                onClick={(e) => {
                  e.stopPropagation();
                  remove(c.id);
                }}
                className="p-1 rounded hover:bg-[var(--bg)]"
                style={{ color: "var(--danger)" }}
              >
                <Trash2 size={13} />
              </button>
            </div>

            {expanded === c.id && (
              <div className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                {!files[c.id] && (
                  <div className="px-4 py-4 flex items-center gap-2 text-xs" style={{ color: "var(--text-dim)" }}>
                    <Loader2 size={12} className="animate-spin" /> Loading files…
                  </div>
                )}
                {files[c.id]?.length === 0 && (
                  <div className="px-4 py-4 text-xs" style={{ color: "var(--text-dim)" }}>
                    No files yet — add some from File Explorer.
                  </div>
                )}
                {files[c.id]?.map((f) => (
                  <div
                    key={f.id}
                    className="flex items-center gap-3 px-4 py-2 text-sm border-t"
                    style={{ borderColor: "var(--panel-border)" }}
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-sm shrink-0"
                      style={{ backgroundColor: CATEGORY_COLORS[f.category] || "#555" }}
                    />
                    <span className="flex-1 truncate" title={f.path}>{f.name}</span>
                    <span className="text-xs mono" style={{ color: "var(--text-dim)" }}>{formatBytes(f.size_bytes)}</span>
                    <button
                      title="Remove from collection"
                      onClick={() => removeFile(c.id, f.id)}
                      className="p-1 rounded hover:bg-[var(--bg)]"
                      style={{ color: "var(--text-dim)" }}
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
