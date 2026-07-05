import { useEffect, useState, useCallback } from "react";
import { Eye, EyeOff, Loader2, AlertTriangle } from "lucide-react";
import { api, type MonitorStatus } from "../lib/api";
import StatCard from "../components/StatCard";

export default function Monitor() {
  const [status, setStatus] = useState<MonitorStatus | null>(null);
  const [path, setPath] = useState("");
  const [autoOrganize, setAutoOrganize] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.monitorStatus().then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function start() {
    if (!path) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.monitorStart(path, autoOrganize);
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start monitor");
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      const s = await api.monitorStop();
      setStatus(s);
    } finally {
      setBusy(false);
    }
  }

  const watching = status?.status === "watching";

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Real-Time Monitoring</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Watches a folder for changes and automatically re-scans new, modified, or deleted files —
          no manual re-scan needed. Uses OS-level file events, not polling.
        </p>
      </div>

      <div
        className="rounded-lg border p-4 flex flex-col gap-3"
        style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
      >
        <div className="flex items-center gap-3">
          <input
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="Folder to watch, e.g. C:\Users\you\Documents"
            disabled={watching}
            className="mono flex-1 bg-transparent text-sm px-3 py-2 rounded-md border outline-none disabled:opacity-50"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          />
          {watching ? (
            <button
              onClick={stop}
              disabled={busy}
              className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-opacity disabled:opacity-50"
              style={{ backgroundColor: "var(--danger)", color: "#fff" }}
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : <EyeOff size={15} />}
              Stop watching
            </button>
          ) : (
            <button
              onClick={start}
              disabled={busy || !path}
              className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-opacity disabled:opacity-50"
              style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
            >
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Eye size={15} />}
              Start watching
            </button>
          )}
        </div>
        <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-dim)" }}>
          <input
            type="checkbox"
            checked={autoOrganize}
            disabled={watching}
            onChange={(e) => setAutoOrganize(e.target.checked)}
          />
          Auto-organize new files into Organized/&lt;Category&gt; as soon as they arrive (e.g. new images move to
          Images, new PDFs move to Documents)
        </label>
      </div>

      {error && (
        <div
          className="flex items-center gap-2 text-sm rounded-md px-3 py-2"
          style={{ backgroundColor: "rgba(180,91,91,0.12)", color: "var(--danger)" }}
        >
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {status && (
        <div className="grid grid-cols-4 gap-3">
          <StatCard
            label="Status"
            value={status.status}
            accent={watching ? "var(--sage)" : status.status === "error" ? "var(--danger)" : undefined}
          />
          <StatCard label="Watching" value={status.root ? status.root.split(/[/\\]/).pop() || status.root : "—"} sub={status.root ?? undefined} />
          <StatCard label="Events processed" value={status.events_processed} />
          <StatCard label="Auto-organized" value={status.auto_organized_count} accent={status.auto_organize ? "var(--purple)" : undefined} />
        </div>
      )}

      {status?.error && (
        <div
          className="flex items-center gap-2 text-sm rounded-md px-3 py-2"
          style={{ backgroundColor: "rgba(180,91,91,0.12)", color: "var(--danger)" }}
        >
          <AlertTriangle size={14} />
          {status.error}
        </div>
      )}

      <div
        className="rounded-lg border border-dashed p-4 text-xs"
        style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
      >
        Changes are debounced by ~2 seconds — a burst of file activity (like copying a folder) is
        batched into one re-scan rather than triggering one per file. Only one folder can be watched
        at a time.
      </div>
    </div>
  );
}

