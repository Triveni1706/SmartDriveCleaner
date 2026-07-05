export default function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  if (confidence === null) return null;
  const pct = Math.round(confidence * 100);
  const color = confidence >= 0.6 ? "var(--sage)" : confidence >= 0.3 ? "var(--clay)" : "var(--text-dim)";
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full mono font-medium"
      style={{
        backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
        color,
      }}
      title="Rule-based heuristic confidence, not a trained ML model"
    >
      <span className="w-1 h-1 rounded-full" style={{ backgroundColor: color }} />
      {pct}%
    </span>
  );
}
