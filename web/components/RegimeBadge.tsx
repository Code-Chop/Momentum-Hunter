const REGIME_META: Record<string, { label: string; tone: string }> = {
  BULL_LOW_VIX:     { label: "Bull · low VIX",     tone: "is-pos" },
  BULL_HIGH_VIX:    { label: "Bull · high VIX",    tone: "is-warn" },
  BULL_EXTREME_VIX: { label: "Bull · extreme VIX", tone: "is-neg" },
  BEAR:             { label: "Bear market",        tone: "is-neg" },
};

export default function RegimeBadge({ regime, vix }: { regime: string | null; vix: string | null }) {
  if (!regime) return null;
  const meta = REGIME_META[regime] ?? { label: regime, tone: "is-neutral" };

  return (
    <span className={`badge ${meta.tone}`}>
      <span className="badge-dot" aria-hidden="true" />
      {meta.label}
      {vix && <span className="num">· VIX {vix}</span>}
    </span>
  );
}
