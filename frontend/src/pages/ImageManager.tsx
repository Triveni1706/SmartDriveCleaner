import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api, formatBytes, type ScannedFile } from "../lib/api";

type Tab = "blurry" | "similar";

export default function ImageManager() {
  const [tab, setTab] = useState<Tab>("blurry");
  const [blurry, setBlurry] = useState<ScannedFile[]>([]);
  const [similar, setSimilar] = useState<ScannedFile[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    Promise.all([api.blurryImages(), api.similarImages()])
      .then(([b, s]) => {
        setBlurry(b);
        setSimilar(s);
      })
      .catch(() => {
        setBlurry([]);
        setSimilar([]);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

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

  const similarGroups = similar.reduce<Record<string, ScannedFile[]>>((acc, f) => {
    const key = f.similar_group || "ungrouped";
    (acc[key] ??= []).push(f);
    return acc;
  }, {});

  const wastedSelected = blurry
    .filter((f) => selected.has(f.id))
    .reduce((sum, f) => sum + f.size_bytes, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Image Manager</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
            Blur detected via OpenCV edge-variance. Similar images via perceptual hashing (near-duplicates, not byte-identical).
          </p>
        </div>
        {tab === "blurry" && selected.size > 0 && (
          <button
            onClick={deleteSelected}
            className="flex items-center gap-2 px-3.5 py-2 rounded-md text-sm font-medium"
            style={{ backgroundColor: "var(--danger)", color: "#fff" }}
          >
            <Trash2 size={14} />
            Move {selected.size} to trash ({formatBytes(wastedSelected)})
          </button>
        )}
      </div>

      <div className="flex gap-1.5">
        <button
          onClick={() => setTab("blurry")}
          className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
          style={{
            backgroundColor: tab === "blurry" ? "var(--panel)" : "transparent",
            color: tab === "blurry" ? "var(--text)" : "var(--text-dim)",
            border: `1px solid ${tab === "blurry" ? "var(--panel-border)" : "transparent"}`,
          }}
        >
          Blurry ({blurry.length})
        </button>
        <button
          onClick={() => setTab("similar")}
          className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
          style={{
            backgroundColor: tab === "similar" ? "var(--panel)" : "transparent",
            color: tab === "similar" ? "var(--text)" : "var(--text-dim)",
            border: `1px solid ${tab === "similar" ? "var(--panel-border)" : "transparent"}`,
          }}
        >
          Similar groups ({Object.keys(similarGroups).length})
        </button>
      </div>

      {tab === "blurry" && (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
          {!loading && blurry.length === 0 && (
            <div className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
              No blurry images detected.
            </div>
          )}
          {blurry.map((f) => (
            <label
              key={f.id}
              className="flex items-center gap-3 px-4 py-2.5 border-t first:border-t-0 text-sm cursor-pointer"
              style={{ borderColor: "var(--panel-border)" }}
            >
              <input
                type="checkbox"
                checked={selected.has(f.id)}
                onChange={() => toggle(f.id)}
                className="accent-[var(--sage)]"
              />
              <span className="flex-1 truncate mono text-xs" style={{ color: "var(--text-dim)" }}>
                {f.path}
              </span>
              <span className="mono text-[11px]" style={{ color: "var(--clay)" }}>
                sharpness {f.blur_score?.toFixed(1)}
              </span>
              <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
                {formatBytes(f.size_bytes)}
              </span>
            </label>
          ))}
        </div>
      )}

      {tab === "similar" && (
        <div className="flex flex-col gap-3">
          {!loading && Object.keys(similarGroups).length === 0 && (
            <div
              className="rounded-lg border border-dashed p-10 text-center text-sm"
              style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
            >
              No similar-image groups found.
            </div>
          )}
          {Object.entries(similarGroups).map(([group, groupFiles]) => (
            <div key={group} className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
              <div
                className="px-4 py-2 text-xs mono"
                style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)" }}
              >
                {groupFiles.length} visually similar images
              </div>
              {groupFiles.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center gap-3 px-4 py-2.5 border-t text-sm"
                  style={{ borderColor: "var(--panel-border)" }}
                >
                  <span className="flex-1 truncate mono text-xs" style={{ color: "var(--text-dim)" }}>
                    {f.path}
                  </span>
                  <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
                    {f.image_width}×{f.image_height}
                  </span>
                  <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
                    {formatBytes(f.size_bytes)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
