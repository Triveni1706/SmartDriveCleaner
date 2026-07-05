import { useEffect, useState } from "react";
import { api, formatBytes, type ScannedFile } from "../lib/api";
import ConfidenceBadge from "../components/ConfidenceBadge";

const SUBCATEGORIES = ["All", "Resume", "Invoice", "Certificate", "Research Paper", "Book", "Notes", "Unclassified"];

export default function PdfManager() {
  const [files, setFiles] = useState<ScannedFile[]>([]);
  const [subcategory, setSubcategory] = useState("All");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .pdfs(subcategory === "All" ? undefined : subcategory)
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }, [subcategory]);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">PDF Manager</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          Classified by filename + first-page content matching — rule-based, not a trained model.
          Confidence badges show how many signals agreed.
        </p>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {SUBCATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setSubcategory(c)}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={{
              backgroundColor: subcategory === c ? "var(--panel)" : "transparent",
              color: subcategory === c ? "var(--text)" : "var(--text-dim)",
              border: `1px solid ${subcategory === c ? "var(--panel-border)" : "transparent"}`,
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
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Name</th>
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Classified as</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Pages</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Size</th>
            </tr>
          </thead>
          <tbody>
            {!loading && files.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
                  No PDFs found for this filter. Run a scan from Overview if you haven't yet.
                </td>
              </tr>
            )}
            {files.map((f) => (
              <tr key={f.id} className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                <td className="px-4 py-2.5 max-w-sm truncate" title={f.path}>
                  {f.name}
                </td>
                <td className="px-4 py-2.5">
                  <span className="flex items-center gap-2 text-xs">
                    {f.subcategory}
                    <ConfidenceBadge confidence={f.subcategory_confidence} />
                  </span>
                </td>
                <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                  {f.pdf_page_count ?? "—"}
                </td>
                <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                  {formatBytes(f.size_bytes)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
