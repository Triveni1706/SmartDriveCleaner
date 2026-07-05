import { motion } from "framer-motion";
import { CATEGORY_COLORS, formatBytes, type StorageStats } from "../lib/api";

export default function StorageStrip({ stats }: { stats: StorageStats }) {
  const entries = Object.entries(stats.by_category).sort((a, b) => b[1].bytes - a[1].bytes);
  const total = stats.total_bytes || 1;

  return (
    <div>
      <div
        className="flex h-9 w-full rounded-xl overflow-hidden p-[3px] gap-[3px]"
        style={{ backgroundColor: "rgba(148,163,184,0.08)", border: "1px solid var(--panel-border)" }}
      >
        {entries.map(([category, data], i) => {
          const pct = (data.bytes / total) * 100;
          if (pct < 0.3) return null;
          const color = CATEGORY_COLORS[category] || "#555";
          return (
            <motion.div
              key={category}
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: `${pct}%`, opacity: 1 }}
              transition={{ duration: 0.7, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
              style={{
                background: `linear-gradient(180deg, color-mix(in srgb, ${color} 92%, white), ${color})`,
                boxShadow: `0 0 8px 0 color-mix(in srgb, ${color} 45%, transparent)`,
              }}
              className="h-full rounded-lg"
              title={`${category}: ${formatBytes(data.bytes)}`}
            />
          );
        })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-3.5">
        {entries.map(([category, data]) => (
          <div key={category} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2 h-2 rounded-[3px] shrink-0"
              style={{ backgroundColor: CATEGORY_COLORS[category] || "#555" }}
            />
            <span style={{ color: "var(--text-dim)" }}>{category}</span>
            <span className="mono" style={{ color: "var(--text)" }}>
              {formatBytes(data.bytes)}
            </span>
            <span className="mono" style={{ color: "var(--text-faint)" }}>
              · {data.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
