const REGIME_STYLES: Record<string, { label: string; color: string }> = {
  BULL_LOW_VIX: { label: "Bull · Low VIX", color: "#1a7f37" },
  BULL_HIGH_VIX: { label: "Bull · High VIX", color: "#9a6700" },
  BULL_EXTREME_VIX: { label: "Bull · Extreme VIX", color: "#cf222e" },
  BEAR: { label: "Bear Market", color: "#cf222e" },
};

export default function RegimeBadge({ regime, vix }: { regime: string | null; vix: string | null }) {
  if (!regime) return null;
  const style = REGIME_STYLES[regime] ?? { label: regime, color: "#57606a" };

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
        color: "#fff",
        backgroundColor: style.color,
      }}
    >
      {style.label}
      {vix ? ` · VIX ${vix}` : ""}
    </span>
  );
}
