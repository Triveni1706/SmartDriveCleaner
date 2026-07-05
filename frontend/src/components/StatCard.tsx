import type { ReactNode } from "react";
import AnimatedNumber from "./AnimatedNumber";

export default function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: string;
}) {
  const color = accent || "var(--text)";

  return (
    <div
      className="glass-card glass-card-hover relative overflow-hidden px-4 py-4 group"
      style={{ borderRadius: "var(--radius-md)" }}
    >
      {/* soft ambient glow tinted with the accent, revealed on hover */}
      <div
        className="pointer-events-none absolute -top-10 -right-10 w-28 h-28 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-2xl"
        style={{ background: color }}
      />

      <div className="relative flex items-center gap-1.5 text-[11.5px] mb-2 font-medium" style={{ color: "var(--text-dim)" }}>
        {accent && (
          <span
            className="relative inline-flex w-1.5 h-1.5 rounded-full shrink-0"
            style={{ backgroundColor: color }}
          >
            <span className="pulse-ring" style={{ color }} />
          </span>
        )}
        {label}
      </div>

      <div className="relative mono text-[26px] leading-none font-semibold tracking-tight" style={{ color }}>
        {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
      </div>

      {sub && (
        <div className="relative text-[11px] mt-1.5" style={{ color: "var(--text-faint)" }}>
          {sub}
        </div>
      )}
    </div>
  );
}
