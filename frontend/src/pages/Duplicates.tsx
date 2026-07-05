import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api, formatBytes, type ScannedFile } from "../lib/api";

export default function Duplicates() {
  const [files, setFiles] = useState<ScannedFile[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    api
      .duplicates()
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  const groups = files.reduce<Record<string, ScannedFile[]>>((acc, f) => {
    const key = f.duplicate_group || "ungrouped";
    (acc[key] ??= []).push(f);
    return acc;
  }, {});

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function deleteSelected() {
    if (selected.size === 0) return;
    await api.trashFiles(Array.from(selected));
    setSelected(new Set());
    load();
  }

  const wastedSelected = files
    .filter((f) => selected.has(f.id))
    .reduce((sum, f) => sum + f.size_bytes, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Duplicates</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
            {Object.keys(groups).length} group{Object.keys(groups).length !== 1 ? "s" : ""} found.
          </p>
        </div>
        {selected.size > 0 && (
          <button
            onClick={deleteSelected}
            className="flex items-center gap-2 px-3.5 py-2 rounded-md text-sm font-medium"
            style={{ backgroundColor: "var(--danger)", color: "#fff" }}
          >
            <Trash2 size={14} />
            Move {selected.size} file{selected.size !== 1 ? "s" : ""} to trash ({formatBytes(wastedSelected)})
          </button>
        )}
      </div>

      {!loading && Object.keys(groups).length === 0 && (
        <div
          className="rounded-lg border border-dashed p-10 text-center text-sm"
          style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
        >
          No duplicates found. Run a scan from the Overview page.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {Object.entries(groups).map(([hash, groupFiles]) => (
          <div
            key={hash}
            className="rounded-lg border overflow-hidden"
            style={{ borderColor: "var(--panel-border)" }}
          >
            <div
              className="px-4 py-2 text-xs mono flex justify-between"
              style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)" }}
            >
              <span>{hash.slice(0, 16)}…</span>
              <span>
                {groupFiles.length} copies · {formatBytes(groupFiles[0]?.size_bytes || 0)} each
              </span>
            </div>
            {groupFiles.map((f) => (
              <label
                key={f.id}
                className="flex items-center gap-3 px-4 py-2.5 border-t text-sm cursor-pointer"
                style={{ borderColor: "var(--panel-border)" }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(f.id)}
                  onChange={() => toggle(f.id)}
                  disabled={!f.is_duplicate}
                  className="accent-[var(--sage)]"
                />
                <span className="flex-1 truncate mono text-xs" style={{ color: "var(--text-dim)" }}>
                  {f.path}
                </span>
                {!f.is_duplicate && (
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded mono"
                    style={{ backgroundColor: "rgba(91,140,123,0.15)", color: "var(--sage)" }}
                  >
                    original
                  </span>
                )}
              </label>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
