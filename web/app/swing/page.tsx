import { getLatestSwingRanking, type SwingPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";
import RegimeBadge from "@/components/RegimeBadge";
import StatTile from "@/components/StatTile";
import ScoreBadge from "@/components/ScoreBadge";

export const dynamic = "force-dynamic";

const columns: Column<SwingPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "score", label: "Momentum", numeric: true, format: (v) => Number(v).toFixed(1) },
  { key: "ai_score", label: "AI Conviction", numeric: true, format: (v) => `${Number(v).toFixed(1)}/10` },
  {
    key: "final_score",
    label: "Final Score",
    numeric: true,
    format: (v) => <ScoreBadge value={Number(v)} />,
  },
];

export default async function SwingPage() {
  let data;
  try {
    data = await getLatestSwingRanking();
  } catch {
    return (
      <div>
        <h1>Daily Swing Picks</h1>
        <p style={{ color: "var(--status-critical)" }}>
          Couldn&apos;t reach the API. It may be waking up from sleep (free-tier cold start) — try again in
          a few seconds.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Daily Swing Picks</h1>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24, alignItems: "center" }}>
        <StatTile label="Picks" value={String(data.picks.length)} />
        <StatTile
          label="Last Scan"
          value={data.scan_time ? new Date(data.scan_time).toLocaleTimeString() : "—"}
          sub={data.scan_time ? new Date(data.scan_time).toLocaleDateString() : undefined}
        />
        <div style={{ display: "flex", alignItems: "center" }}>
          <RegimeBadge regime={data.regime} vix={data.vix} />
        </div>
      </div>

      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
