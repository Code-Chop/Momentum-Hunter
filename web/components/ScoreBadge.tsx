const STEPS = [
  { max: 0.2, bg: "var(--seq-100)", fg: "#0b0b0b" },
  { max: 0.4, bg: "var(--seq-250)", fg: "#0b0b0b" },
  { max: 0.6, bg: "var(--seq-400)", fg: "#ffffff" },
  { max: 0.8, bg: "var(--seq-500)", fg: "#ffffff" },
  { max: Infinity, bg: "var(--seq-650)", fg: "#ffffff" },
];

/** Sequential-blue score pill: darker fill = higher magnitude within [min, max]. */
export default function ScoreBadge({
  value,
  min = -60,
  max = 100,
}: {
  value: number;
  min?: number;
  max?: number;
}) {
  const t = Math.min(1, Math.max(0, (value - min) / (max - min)));
  const step = STEPS.find((s) => t <= s.max) ?? STEPS[STEPS.length - 1];

  return (
    <span
      className="tabular-nums"
      style={{
        display: "inline-block",
        minWidth: 46,
        textAlign: "center",
        padding: "3px 8px",
        borderRadius: 6,
        fontWeight: 600,
        fontSize: 13,
        background: step.bg,
        color: step.fg,
      }}
    >
      {value.toFixed(1)}
    </span>
  );
}
