import { useEffect, useRef, useState } from "react";
import { Send, Loader2, FileDown, Clock, Plus, Trash2, Play } from "lucide-react";
import { api, formatBytes, type ScheduledJob, type ScheduledRun, type AuditLogEntry } from "../lib/api";

type ChatMessage = { role: "user" | "assistant"; text: string };

const CHAT_EXAMPLES = [
  "which files consume the most storage",
  "which files should I delete",
  "which files are unused",
  "how many duplicates do I have",
];

const FREQUENCIES = ["daily", "weekly", "monthly"] as const;

export default function Assistant() {
  return (
    <div className="flex flex-col gap-8 max-w-5xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Assistant</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Ask questions about your scan, schedule recurring cleanups, generate reports, and review
          what's happened automatically.
        </p>
      </div>
      <ChatPanel />
      <SchedulerPanel />
      <AuditPanel />
    </div>
  );
}

function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const r = await api.chat(text);
      setMessages((m) => [...m, { role: "assistant", text: r.reply }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Something went wrong reaching the assistant." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
      <div className="px-4 py-2.5 text-xs font-medium" style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)" }}>
        Chat
      </div>
      <div className="flex flex-col gap-3 p-4 max-h-80 overflow-y-auto">
        {messages.length === 0 && (
          <div className="flex gap-1.5 flex-wrap">
            {CHAT_EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => send(ex)}
                className="px-2.5 py-1 rounded-md text-[11px] mono"
                style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)", border: "1px solid var(--panel-border)" }}
              >
                {ex}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className="text-sm whitespace-pre-wrap px-3 py-2 rounded-md max-w-[85%]"
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              backgroundColor: m.role === "user" ? "var(--sage)" : "var(--panel)",
              color: m.role === "user" ? "#0B0D0F" : "var(--text)",
            }}
          >
            {m.text}
          </div>
        ))}
        {loading && <Loader2 size={14} className="animate-spin" style={{ color: "var(--text-dim)" }} />}
        <div ref={bottomRef} />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 p-3 border-t"
        style={{ borderColor: "var(--panel-border)" }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your drive…"
          className="flex-1 bg-transparent text-sm px-3 py-2 rounded-md border outline-none"
          style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="p-2 rounded-md disabled:opacity-50"
          style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
        >
          <Send size={15} />
        </button>
      </form>
    </div>
  );
}

function SchedulerPanel() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [runs, setRuns] = useState<ScheduledRun[]>([]);
  const [jobName, setJobName] = useState("cleanup_job");
  const [frequency, setFrequency] = useState<(typeof FREQUENCIES)[number]>("weekly");
  const [autoClean, setAutoClean] = useState(false);
  const [reportBusy, setReportBusy] = useState(false);

  function load() {
    api.listJobs().then(setJobs).catch(() => {});
    api.listRuns().then(setRuns).catch(() => {});
  }

  useEffect(load, []);

  async function addJob() {
    if (!jobName.trim()) return;
    await api.scheduleJob(jobName.trim(), frequency, autoClean);
    load();
  }

  async function removeJob(name: string) {
    await api.deleteJob(name);
    load();
  }

  async function runNow(name: string) {
    await api.runJobNow(name);
    load();
  }

  async function generateReport() {
    setReportBusy(true);
    try {
      const { filename } = await api.generateReport();
      window.open(api.reportDownloadUrl(filename), "_blank");
    } finally {
      setReportBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Cleanup Scheduler & Reports</h2>
        <button
          onClick={generateReport}
          disabled={reportBusy}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium disabled:opacity-50"
          style={{ backgroundColor: "var(--panel)", border: "1px solid var(--panel-border)", color: "var(--text)" }}
        >
          {reportBusy ? <Loader2 size={13} className="animate-spin" /> : <FileDown size={13} />}
          Generate PDF report now
        </button>
      </div>

      <div
        className="rounded-lg border p-4 flex items-end gap-3 flex-wrap"
        style={{ backgroundColor: "var(--panel)", borderColor: "var(--panel-border)" }}
      >
        <div className="flex flex-col gap-1">
          <label className="text-[11px]" style={{ color: "var(--text-dim)" }}>Job name</label>
          <input
            value={jobName}
            onChange={(e) => setJobName(e.target.value)}
            className="mono text-sm px-2.5 py-1.5 rounded-md border outline-none bg-transparent"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px]" style={{ color: "var(--text-dim)" }}>Frequency</label>
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as typeof frequency)}
            className="text-sm px-2.5 py-1.5 rounded-md border outline-none bg-transparent"
            style={{ borderColor: "var(--panel-border)", color: "var(--text)" }}
          >
            {FREQUENCIES.map((f) => (
              <option key={f} value={f} style={{ backgroundColor: "#0B0D0F" }}>{f}</option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-xs pb-2" style={{ color: "var(--text-dim)" }}>
          <input type="checkbox" checked={autoClean} onChange={(e) => setAutoClean(e.target.checked)} />
          Auto-delete exact duplicates
        </label>
        <button
          onClick={addJob}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium"
          style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
        >
          <Plus size={13} /> Add job
        </button>
      </div>

      {jobs.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {jobs.map((j) => (
            <div
              key={j.job_name}
              className="flex items-center justify-between px-3 py-2 rounded-md text-sm"
              style={{ backgroundColor: "var(--panel)", border: "1px solid var(--panel-border)" }}
            >
              <span className="mono">{j.job_name}</span>
              <span className="text-xs" style={{ color: "var(--text-dim)" }}>
                {j.frequency}{j.auto_clean_duplicates ? " · auto-clean duplicates" : ""}
              </span>
              <div className="flex items-center gap-1.5">
                <button onClick={() => runNow(j.job_name)} title="Run now" className="p-1.5 rounded-md hover:opacity-70">
                  <Play size={13} style={{ color: "var(--sage)" }} />
                </button>
                <button onClick={() => removeJob(j.job_name)} title="Remove" className="p-1.5 rounded-md hover:opacity-70">
                  <Trash2 size={13} style={{ color: "var(--danger)" }} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {runs.length > 0 && (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
          <div className="px-4 py-2 text-xs" style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)" }}>
            Run history
          </div>
          {runs.slice(0, 10).map((r) => (
            <div key={r.id} className="flex items-center gap-3 px-4 py-2 border-t text-xs" style={{ borderColor: "var(--panel-border)" }}>
              <Clock size={12} style={{ color: "var(--text-dim)" }} />
              <span className="mono" style={{ color: "var(--text-dim)" }}>{new Date(r.ran_at).toLocaleString()}</span>
              <span className="flex-1">{r.job_name}</span>
              <span style={{ color: "var(--clay)" }}>{r.files_affected} files, {formatBytes(r.bytes_recovered)} freed</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AuditPanel() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    api.auditLog(50).then(setLogs).catch(() => {});
  }, []);

  if (logs.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold">Activity Log</h2>
      <div className="rounded-lg border overflow-hidden max-h-72 overflow-y-auto" style={{ borderColor: "var(--panel-border)" }}>
        {logs.map((l) => (
          <div key={l.id} className="flex items-center gap-3 px-4 py-2 border-t first:border-t-0 text-xs" style={{ borderColor: "var(--panel-border)" }}>
            <span className="mono" style={{ color: "var(--text-dim)" }}>{new Date(l.timestamp).toLocaleString()}</span>
            <span className="px-1.5 py-0.5 rounded mono" style={{ backgroundColor: "rgba(122,156,198,0.15)", color: "var(--purple, #7A9CC6)" }}>
              {l.action}
            </span>
            <span className="flex-1 truncate" style={{ color: "var(--text-dim)" }}>{l.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
