import { getLatestIntradayWatchlist, type IntradayPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";

export const dynamic = "force-dynamic";

const columns: Column<IntradayPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "last_close", label: "Last Close", format: (v) => `₹${Number(v).toFixed(2)}` },
  { key: "return_pct", label: "Return %", format: (v) => `${Number(v).toFixed(2)}%` },
  { key: "volume_ratio", label: "Vol Ratio", format: (v) => `${Number(v).toFixed(2)}x` },
  { key: "breakout", label: "Breakout", format: (v) => (v ? "✅" : "❌") },
  { key: "above_vwap", label: "Above VWAP", format: (v) => (v ? "✅" : "❌") },
  {
    key: "rs_vs_nifty",
    label: "RS vs Nifty",
    format: (v) => (v === null ? "N/A" : `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`),
  },
  { key: "ai_score", label: "AI Conviction", format: (v) => `${Number(v).toFixed(1)}/10` },
  { key: "final_score", label: "Final Score", format: (v) => Number(v).toFixed(1) },
];

export default async function IntradayPage() {
  let data;
  try {
    data = await getLatestIntradayWatchlist();
  } catch {
    return (
      <div>
        <h1>Intraday Watchlist</h1>
        <p style={{ color: "#cf222e" }}>
          Couldn&apos;t reach the API. It may be waking up from sleep (free-tier cold start) — try again in
          a few seconds.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Intraday Watchlist</h1>
      {data.scan_time && (
        <p style={{ color: "#57606a" }}>Last scan: {new Date(data.scan_time).toLocaleString()}</p>
      )}
      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
