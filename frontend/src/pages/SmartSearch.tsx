import { useEffect, useState } from "react";
import { Search, Loader2, Database } from "lucide-react";
import { api, formatBytes, type SearchResponse, type SearchIndexStatus } from "../lib/api";

const EXAMPLES = [
  "show invoices from 2025",
  "screenshots older than 6 months",
  "duplicate files",
  "images larger than 5mb",
  "resumes",
];

export default function SmartSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [indexStatus, setIndexStatus] = useState<SearchIndexStatus | null>(null);

  useEffect(() => {
    api.searchStatus().then(setIndexStatus).catch(() => setIndexStatus(null));
  }, []);

  async function runSearch(q: string) {
    if (!q.trim()) return;
    setQuery(q);
    setLoading(true);
    try {
      const r = await api.search(q);
      setResult(r);
    } catch {
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Smart Search</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Natural language search over your scanned files — try category, date range, size, or
          duplicate/blur status. Rule-based parsing, not a black box: it shows exactly what it matched.
        </p>
      </div>

      {indexStatus && (
        <div
          className="flex items-center gap-5 text-xs mono px-3 py-2 rounded-md"
          style={{ backgroundColor: "var(--panel)", border: "1px solid var(--panel-border)", color: "var(--text-dim)" }}
        >
          <span className="flex items-center gap-1.5">
            <Database size={12} style={{ color: "var(--sage)" }} />
            Indexed Files: <span style={{ color: "var(--text)" }}>{indexStatus.indexed_files.toLocaleString()}</span>
          </span>
          <span>
            Last Scan:{" "}
            <span style={{ color: "var(--text)" }}>
              {indexStatus.last_scan ? new Date(indexStatus.last_scan).toLocaleString() : "never"}
            </span>
          </span>
          <span>
            Status:{" "}
            <span
              style={{
                color: indexStatus.status === "ready" ? "var(--sage)" : "var(--text-dim)",
                textTransform: "capitalize",
              }}
            >
              {indexStatus.status}
            </span>
          </span>
          <span style={{ marginLeft: "auto" }}>Search is served entirely from the index — no rescan needed.</span>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(query);
        }}
        className="flex items-center gap-3"
      >
        <div
          className="flex-1 flex items-center gap-2 rounded-md border px-3 py-2"
          style={{ borderColor: "var(--panel-border)", backgroundColor: "var(--panel)" }}
        >
          <Search size={15} style={{ color: "var(--text-dim)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='e.g. "show invoices from 2025" or "screenshots older than 6 months"'
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--text)" }}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium disabled:opacity-50"
          style={{ backgroundColor: "var(--sage)", color: "#0B0D0F" }}
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
          Search
        </button>
      </form>

      <div className="flex gap-1.5 flex-wrap">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => runSearch(ex)}
            className="px-2.5 py-1 rounded-md text-[11px] mono transition-colors"
            style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)", border: "1px solid var(--panel-border)" }}
          >
            {ex}
          </button>
        ))}
      </div>

      {result && (
        <>
          <div
            className="text-xs px-3 py-2 rounded-md mono"
            style={{ backgroundColor: "var(--panel)", color: "var(--text-dim)" }}
          >
            Interpreted as: {result.interpreted_as} — {result.results.length} result
            {result.results.length !== 1 ? "s" : ""}
          </div>

          <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ backgroundColor: "var(--panel)" }} className="text-left">
                  <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Name</th>
                  <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Category</th>
                  <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Size</th>
                </tr>
              </thead>
              <tbody>
                {result.results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
                      No matches.
                    </td>
                  </tr>
                )}
                {result.results.map((f) => (
                  <tr key={f.id} className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                    <td className="px-4 py-2.5 max-w-sm truncate" title={f.path}>{f.name}</td>
                    <td className="px-4 py-2.5 text-xs" style={{ color: "var(--text-dim)" }}>{f.category}</td>
                    <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                      {formatBytes(f.size_bytes)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
