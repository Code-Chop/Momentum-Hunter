import { getLatestIntradayWatchlist, type IntradayPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";
import StatTile from "@/components/StatTile";
import ScoreBadge from "@/components/ScoreBadge";

export const dynamic = "force-dynamic";

const columns: Column<IntradayPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "last_close", label: "Last Close", numeric: true, format: (v) => `₹${Number(v).toFixed(2)}` },
  { key: "return_pct", label: "Return %", numeric: true, format: (v) => `${Number(v).toFixed(2)}%` },
  { key: "volume_ratio", label: "Vol Ratio", numeric: true, format: (v) => `${Number(v).toFixed(2)}x` },
  { key: "breakout", label: "Breakout", format: (v) => (v ? "✅" : "—") },
  { key: "above_vwap", label: "Above VWAP", format: (v) => (v ? "✅" : "—") },
  {
    key: "rs_vs_nifty",
    label: "RS vs Nifty",
    numeric: true,
    format: (v) => (v === null ? "N/A" : `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`),
  },
  { key: "ai_score", label: "AI Conviction", numeric: true, format: (v) => `${Number(v).toFixed(1)}/10` },
  {
    key: "final_score",
    label: "Final Score",
    numeric: true,
    format: (v) => <ScoreBadge value={Number(v)} max={120} />,
  },
];

export default async function IntradayPage() {
  let data;
  try {
    data = await getLatestIntradayWatchlist();
  } catch {
    return (
      <div>
        <h1>Intraday Watchlist</h1>
        <p style={{ color: "var(--status-critical)" }}>
          Couldn&apos;t reach the API. It may be waking up from sleep (free-tier cold start) — try again in
          a few seconds.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Intraday Watchlist</h1>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
        <StatTile label="Picks" value={String(data.picks.length)} />
        <StatTile
          label="Last Scan"
          value={data.scan_time ? new Date(data.scan_time).toLocaleTimeString() : "—"}
          sub={data.scan_time ? new Date(data.scan_time).toLocaleDateString() : undefined}
        />
      </div>

      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
