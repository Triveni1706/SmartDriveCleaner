export default function ProgressBar({
  percent,
  indeterminate = false,
  accent = "var(--sage)",
}: {
  percent: number | null;
  indeterminate?: boolean;
  accent?: string;
}) {
  return (
    <div
      className="relative h-2 w-full rounded-full overflow-hidden"
      style={{ backgroundColor: "rgba(148,163,184,0.12)" }}
    >
      <div
        className={
          indeterminate
            ? "h-full rounded-full animate-pulse"
            : "h-full rounded-full transition-[width] duration-500 ease-out"
        }
        style={{
          width: indeterminate ? "40%" : `${Math.min(Math.max(percent ?? 0, 2), 100)}%`,
          background: `linear-gradient(90deg, ${accent}, color-mix(in srgb, ${accent} 55%, white))`,
          boxShadow: `0 0 10px 0 color-mix(in srgb, ${accent} 60%, transparent)`,
        }}
      />
    </div>
  );
}
