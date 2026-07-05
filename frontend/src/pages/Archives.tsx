import { useEffect, useState } from "react";
import { api, formatBytes, type ScannedFile } from "../lib/api";

export default function Archives() {
  const [files, setFiles] = useState<ScannedFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .archives()
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">Archives</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-dim)" }}>
          ZIP contents are fully inspected. RAR/7Z show size only unless the optional
          system tools are installed.
        </p>
      </div>

      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--panel-border)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--panel)" }} className="text-left">
              <th className="px-4 py-2.5 font-medium text-xs" style={{ color: "var(--text-dim)" }}>Name</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Contains</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Uncompressed</th>
              <th className="px-4 py-2.5 font-medium text-xs text-right" style={{ color: "var(--text-dim)" }}>Archive size</th>
            </tr>
          </thead>
          <tbody>
            {!loading && files.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm" style={{ color: "var(--text-dim)" }}>
                  No archives found.
                </td>
              </tr>
            )}
            {files.map((f) => (
              <tr key={f.id} className="border-t" style={{ borderColor: "var(--panel-border)" }}>
                <td className="px-4 py-2.5 max-w-sm truncate" title={f.path}>
                  {f.name}
                </td>
                <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                  {f.archive_file_count !== null ? `${f.archive_file_count} files` : "—"}
                </td>
                <td className="px-4 py-2.5 mono text-right text-xs" style={{ color: "var(--text-dim)" }}>
                  {f.archive_uncompressed_bytes !== null ? formatBytes(f.archive_uncompressed_bytes) : "—"}
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
