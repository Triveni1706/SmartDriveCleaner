import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Loader2, ScanLine, AlertTriangle, CheckSquare, Square, Sparkles, Clock,
  Image as ImageIcon, FileText, Video, Music, Archive, FolderOpen, File as FileIcon,
} from "lucide-react";
import { api, formatBytes, pollJob, type CategoryStatsResponse, type JobStatus } from "../lib/api";
import ProgressBar from "../components/ProgressBar";

const CATEGORY_ICONS: Record<string, any> = {
  Images: ImageIcon,
  PDFs: FileText,
  Videos: Video,
  Audio: Music,
  Archives: Archive,
  Documents: FolderOpen,
  Others: FileIcon,
};

type Stage = "idle" | "quick_scanning" | "picking" | "deep_scanning" | "done";

export default function Overview() {
  const [path, setPath] = useState("");
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);

  const [quickJob, setQuickJob] = useState<JobStatus | null>(null);
  const [stats, setStats] = useState<CategoryStatsResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [deepJob, setDeepJob] = useState<JobStatus | null>(null);

  const loadCategoryStats = useCallback(async () => {
    const s = await api.categoryStats();
    setStats(s);
    return s;
  }, []);

  async function handleQuickScan() {
    setError(null);
    setStage("quick_scanning");
    setQuickJob(null);
    setDeepJob(null);
    try {
      const { job_id } = await api.quickScan(path);
      const final = await pollJob(job_id, setQuickJob, 400);
      if (final.status === "error") {
        setError(final.error || "Quick scan failed");
        setStage("idle");
        return;
      }
      const s = await loadCategoryStats();
      // Sensible default: pre-check the two biggest analyzable categories so
      // a first-time user isn't staring at every box unticked or all of them.
      const defaults = s.categories
        .filter((c) => c.supports_deep_analysis && c.file_count > 0)
        .slice(0, 2)
        .map((c) => c.category);
      setSelected(new Set(defaults));
      setStage("picking");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Quick scan failed");
      setStage("idle");
    }
  }

  function toggleCategory(category: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(category) ? next.delete(category) : next.add(category);
      return next;
    });
  }

  async function handleDeepScan() {
    if (selected.size === 0) return;
    setError(null);
    setStage("deep_scanning");
    setDeepJob(null);
    try {
      const { job_id } = await api.deepScan(Array.from(selected));
      const final = await pollJob(job_id, setDeepJob, 400);
      if (final.status === "error") {
        setError(final.error || "Analysis failed");
        setStage("picking");
        return;
      }
      await loadCategoryStats();
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setStage("picking");
    }
  }

  const selectedEstimateSeconds =
    stats?.categories
      .filter((c) => selected.has(c.category))
      .reduce((sum, c) => sum + c.estimated_seconds, 0) ?? 0;

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Overview</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Quick scan finds what's on disk in seconds. Then pick exactly what to analyze deeply.
        </p>
      </div>

      {/* Path input + quick scan trigger */}
      <div
        className="rounded-lg border p-4 flex items-center gap-3"
        style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
      >
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="C:\Users\you\Downloads or /home/you/Downloads"
          className="mono flex-1 bg-transparent text-sm px-3 py-2 rounded-md border outline-none"
          style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          disabled={stage === "quick_scanning" || stage === "deep_scanning"}
        />
        <button
          onClick={handleQuickScan}
          disabled={stage === "quick_scanning" || stage === "deep_scanning" || !path}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-opacity disabled:opacity-50"
          style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
        >
          {stage === "quick_scanning" ? <Loader2 size={15} className="animate-spin" /> : <ScanLine size={15} />}
          {stage === "quick_scanning" ? "Scanning…" : "Quick scan"}
        </button>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-sm rounded-md px-3 py-2"
            style={{ backgroundColor: "rgba(180,91,91,0.12)", color: "var(--danger)" }}
          >
            <AlertTriangle size={14} />
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stage 1 progress */}
      {stage === "quick_scanning" && (
        <div
          className="rounded-lg border p-4 flex flex-col gap-2"
          style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
        >
          <div className="flex items-center justify-between text-sm">
            <span>{quickJob?.current_task ?? "Starting…"}</span>
            <span className="mono" style={{ color: "var(--text-dim)" }}>
              metadata only — no hashing, no AI
            </span>
          </div>
          <ProgressBar percent={null} indeterminate accent="var(--sage)" />
        </div>
      )}

      {/* Stage 1 results: category picker */}
      {stats && (stage === "picking" || stage === "deep_scanning" || stage === "done") && (
        <div
          className="rounded-lg border p-4 flex flex-col gap-4"
          style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">
                {stats.total_files.toLocaleString()} files · {formatBytes(stats.total_bytes)}
              </div>
              <div className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>
                Choose which categories to run deep analysis on (duplicates, near-duplicates, blur, classification).
              </div>
            </div>
            {selected.size > 0 && stage === "picking" && (
              <div className="flex items-center gap-1.5 text-xs mono" style={{ color: "var(--text-dim)" }}>
                <Clock size={13} />
                ~{selectedEstimateSeconds < 1 ? "<1" : Math.round(selectedEstimateSeconds)}s estimated
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {stats.categories.map((c) => {
              const Icon = CATEGORY_ICONS[c.category] || FileIcon;
              const isChecked = selected.has(c.category);
              const disabled = !c.supports_deep_analysis || stage !== "picking";
              return (
                <button
                  key={c.category}
                  onClick={() => c.supports_deep_analysis && stage === "picking" && toggleCategory(c.category)}
                  disabled={disabled}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md border text-left transition-colors disabled:cursor-default"
                  style={{
                    borderColor: "var(--panel-border)",
                    backgroundColor: isChecked ? "rgba(91,140,123,0.10)" : "transparent",
                  }}
                >
                  {isChecked ? (
                    <CheckSquare size={16} style={{ color: "var(--sage)" }} />
                  ) : (
                    <Square size={16} style={{ color: c.supports_deep_analysis ? "var(--text-dim)" : "#454b50" }} />
                  )}
                  <Icon size={15} style={{ color: "var(--text-dim)" }} />
                  <span className="text-sm flex-1">{c.category}</span>
                  <span className="mono text-xs" style={{ color: "var(--text-dim)" }}>
                    {c.file_count.toLocaleString()} files
                  </span>
                  <span className="mono text-xs w-16 text-right" style={{ color: "var(--text-dim)" }}>
                    {formatBytes(c.total_bytes)}
                  </span>
                  <span className="mono text-xs w-14 text-right" style={{ color: "var(--text-dim)" }}>
                    ~{c.estimated_seconds < 1 ? "<1" : Math.round(c.estimated_seconds)}s
                  </span>
                  {!c.supports_deep_analysis && (
                    <span className="text-[10px]" style={{ color: "var(--text-dim)" }}>
                      no analysis available
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {stage === "picking" && (
            <button
              onClick={handleDeepScan}
              disabled={selected.size === 0}
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-opacity disabled:opacity-40 self-start"
              style={{ backgroundColor: "var(--clay)", color: "#0B0D0F" }}
            >
              <Sparkles size={15} />
              Analyze {selected.size > 0 ? `${selected.size} selected ` : ""}categor{selected.size === 1 ? "y" : "ies"}
            </button>
          )}

          {stage === "deep_scanning" && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <Loader2 size={14} className="animate-spin" style={{ color: "var(--clay)" }} />
                  {deepJob?.current_task ?? "Starting…"}
                </span>
                <span className="mono" style={{ color: "var(--text-dim)" }}>
                  {deepJob ? `${deepJob.completed_items.toLocaleString()} / ${deepJob.total_items.toLocaleString()}` : ""}
                  {deepJob?.eta_seconds != null ? ` · ~${Math.round(deepJob.eta_seconds)}s left` : ""}
                </span>
              </div>
              <ProgressBar percent={deepJob?.percent ?? 0} accent="var(--clay)" />
            </div>
          )}

          {stage === "done" && deepJob?.result && (
            <DeepScanSummary result={deepJob.result} onRescan={() => setStage("picking")} />
          )}
        </div>
      )}

      {!stats && stage === "idle" && (
        <div
          className="rounded-lg border border-dashed p-10 text-center text-sm"
          style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
        >
          No scan data yet. Enter a folder path above and run a quick scan.
        </div>
      )}
    </div>
  );
}

function DeepScanSummary({ result, onRescan }: { result: Record<string, any>; onRescan: () => void }) {
  const byCategory: Record<string, any> = result.by_category || {};
  const entries = Object.entries(byCategory);
  const totalDupBytes = entries.reduce((sum, [, v]: [string, any]) => sum + (v.duplicate_wasted_bytes || 0), 0);

  return (
    <div className="flex flex-col gap-3 pt-1 border-t" style={{ borderColor: "var(--panel-border)" }}>
      <div className="text-sm font-medium pt-3">
        Analyzed {result.files_analyzed?.toLocaleString?.() ?? result.files_analyzed} files ·{" "}
        <span style={{ color: "var(--clay)" }}>{formatBytes(totalDupBytes)} recoverable</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {entries.map(([category, v]: [string, any]) => (
          <div
            key={category}
            className="rounded-md border px-3 py-2 text-xs flex flex-col gap-0.5"
            style={{ borderColor: "var(--panel-border)" }}
          >
            <span className="font-medium text-[13px]">{category}</span>
            <span style={{ color: "var(--text-dim)" }}>
              {v.duplicate_groups ?? 0} duplicate group(s)
              {v.similar_image_groups != null ? ` · ${v.similar_image_groups} similar group(s)` : ""}
            </span>
            {v.duplicate_wasted_bytes > 0 && (
              <span className="mono" style={{ color: "var(--clay)" }}>
                {formatBytes(v.duplicate_wasted_bytes)} wasted
              </span>
            )}
          </div>
        ))}
      </div>
      <button
        onClick={onRescan}
        className="text-xs self-start px-3 py-1.5 rounded-md border"
        style={{ borderColor: "var(--panel-border)", color: "var(--text-dim)" }}
      >
        Choose different categories
      </button>
    </div>
  );
}
