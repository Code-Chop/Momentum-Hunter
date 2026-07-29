const REGIME_META: Record<string, { label: string; icon: string; color: string }> = {
  BULL_LOW_VIX:     { label: "Bull · Low VIX",      icon: "▲", color: "var(--status-good)" },
  BULL_HIGH_VIX:    { label: "Bull · High VIX",     icon: "!", color: "var(--status-warning)" },
  BULL_EXTREME_VIX: { label: "Bull · Extreme VIX",  icon: "!", color: "var(--status-serious)" },
  BEAR:             { label: "Bear Market",         icon: "▼", color: "var(--status-critical)" },
};

export default function RegimeBadge({ regime, vix }: { regime: string | null; vix: string | null }) {
  if (!regime) return null;
  const meta = REGIME_META[regime] ?? { label: regime, icon: "•", color: "var(--text-secondary)" };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
        color: meta.color,
        border: `1px solid ${meta.color}`,
        background: "var(--surface-1)",
      }}
    >
      <span aria-hidden="true">{meta.icon}</span>
      {meta.label}
      {vix ? ` · VIX ${vix}` : ""}
    </span>
  );
}
