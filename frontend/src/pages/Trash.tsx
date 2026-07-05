import { useEffect, useState } from "react";
import { RotateCcw, Trash2, Loader2, Undo2 } from "lucide-react";
import { api, formatBytes, type TrashItemOut } from "../lib/api";

export default function Trash() {
  const [items, setItems] = useState<TrashItemOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  function load() {
    setLoading(true);
    api
      .listTrash()
      .then(setItems)
      .catch(() => setItems([]))
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

  async function restoreSelected() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      await api.restoreFromTrash(Array.from(selected));
      setSelected(new Set());
      load();
    } finally {
      setBusy(false);
    }
  }

  async function purgeSelected() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      await api.purgeTrash(Array.from(selected));
      setSelected(new Set());
      load();
    } finally {
      setBusy(false);
    }
  }

  async function emptyAll() {
    setBusy(true);
    try {
      await api.emptyTrash();
      setSelected(new Set());
      load();
    } finally {
      setBusy(false);
    }
  }

  const totalBytes = items.reduce((sum, i) => sum + i.size_bytes, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Recovery Center</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
            {items.length} item{items.length !== 1 ? "s" : ""} in trash · {formatBytes(totalBytes)}. Deleted files
            land here first — nothing is removed from disk permanently until you say so.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <>
              <button
                onClick={restoreSelected}
                disabled={busy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
                style={{ backgroundColor: "var(--sage)", color: "#fff" }}
              >
                {busy ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                Restore {selected.size}
              </button>
              <button
                onClick={purgeSelected}
                disabled={busy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
                style={{ backgroundColor: "var(--danger)", color: "#fff" }}
              >
                <Trash2 size={12} />
                Delete permanently
              </button>
            </>
          )}
          {items.length > 0 && (
            <button
              onClick={emptyAll}
              disabled={busy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
              style={{ backgroundColor: "transparent", color: "var(--danger)", border: "1px solid var(--panel-border)" }}
            >
              Empty trash
            </button>
          )}
        </div>
      </div>

      {!loading && items.length === 0 && (
        <div
          className="rounded-lg border border-dashed p-10 text-center text-sm"
          style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
        >
          Trash is empty. Files you delete from File Explorer, Duplicates, Image Manager, or Recommendations show up
          here before they're gone for good.
        </div>
      )}

      {items.length > 0 && (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: "var(--panel)" }} className="text-left">
                <th className="px-3 py-2.5 w-8">
                  <input
                    type="checkbox"
                    className="accent-[var(--sage)]"
                    checked={selected.size === items.length}
                    onChange={() =>
                      setSelected((prev) => (prev.size === items.length ? new Set() : new Set(items.map((i) => i.id))))
                    }
                  />
                </th>
                <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Name</th>
                <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Original location</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Size</th>
                <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Deleted</th>
                <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                  <td className="px-3 py-2.5">
                    <input
                      type="checkbox"
                      className="accent-[var(--sage)]"
                      checked={selected.has(item.id)}
                      onChange={() => toggle(item.id)}
                    />
                  </td>
                  <td className="px-4 py-2.5 max-w-xs truncate">{item.file_name}</td>
                  <td className="px-4 py-2.5 max-w-xs truncate mono text-xs" style={{ color: "var(--text-dim)" }} title={item.original_path}>
                    {item.original_path}
                  </td>
                  <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                    {formatBytes(item.size_bytes)}
                  </td>
                  <td className="px-4 py-2.5 mono text-xs" style={{ color: "var(--text-dim)" }}>
                    {new Date(item.deleted_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        title="Restore"
                        onClick={async () => {
                          setBusy(true);
                          try {
                            await api.restoreFromTrash([item.id]);
                            load();
                          } finally {
                            setBusy(false);
                          }
                        }}
                        className="p-1.5 rounded-md hover:bg-[var(--bg)]"
                        style={{ color: "var(--sage)" }}
                      >
                        <Undo2 size={13} />
                      </button>
                      <button
                        title="Delete permanently"
                        onClick={async () => {
                          setBusy(true);
                          try {
                            await api.purgeTrash([item.id]);
                            load();
                          } finally {
                            setBusy(false);
                          }
                        }}
                        className="p-1.5 rounded-md hover:bg-[var(--bg)]"
                        style={{ color: "var(--danger)" }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
