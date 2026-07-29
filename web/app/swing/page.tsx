import { getLatestSwingRanking, type SwingPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";
import RegimeBadge from "@/components/RegimeBadge";
import StatTile from "@/components/StatTile";

export const dynamic = "force-dynamic";

const columns: Column<SwingPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "score", label: "Momentum", numeric: true, format: (v) => Number(v).toFixed(1) },
  {
    key: "ai_score",
    label: "AI conviction",
    numeric: true,
    format: (v) =>
      Number(v) > 0 ? `${Number(v).toFixed(1)} / 10` : <span style={{ color: "var(--ink-muted)" }}>—</span>,
  },
  { key: "final_score", label: "Final score", meter: true },
];

export default async function SwingPage() {
  let data;
  try {
    data = await getLatestSwingRanking();
  } catch {
    return (
      <div>
        <div className="page-head">
          <span className="label">Daily scan</span>
          <h1>Swing picks</h1>
        </div>
        <div className="empty">
          Couldn&apos;t reach the API — free-tier instances sleep when idle and take ~30s to wake.
          Refresh in a moment.
        </div>
      </div>
    );
  }

  const scored = data.picks.filter((p) => p.ai_score > 0).length;

  return (
    <div>
      <div className="page-head">
        <span className="label">Daily scan · after market close</span>
        <h1>Swing picks</h1>
        <p className="page-sub">
          The full Nifty 500 ranked on multi-timeframe momentum, with an LLM conviction score blended into
          the top candidates. Sorted by final score.
        </p>
      </div>

      <div className="tile-row">
        <StatTile label="Ranked" value={String(data.picks.length)} sub="stocks scored" />
        <StatTile label="AI reviewed" value={String(scored)} sub="top candidates" />
        <StatTile
          label="Last scan"
          value={data.scan_time ? new Date(data.scan_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
          sub={data.scan_time ? new Date(data.scan_time).toLocaleDateString() : undefined}
        />
        <div className="tile" style={{ justifyContent: "center" }}>
          <span className="label">Regime</span>
          <span style={{ marginTop: 2 }}>
            <RegimeBadge regime={data.regime} vix={data.vix} />
          </span>
        </div>
      </div>

      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
