import { getLatestSwingRanking, type SwingPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";
import RegimeBadge from "@/components/RegimeBadge";

export const dynamic = "force-dynamic";

const columns: Column<SwingPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "score", label: "Momentum Score", format: (v) => Number(v).toFixed(1) },
  { key: "ai_score", label: "AI Conviction", format: (v) => `${Number(v).toFixed(1)}/10` },
  { key: "final_score", label: "Final Score", format: (v) => Number(v).toFixed(1) },
];

export default async function SwingPage() {
  let data;
  try {
    data = await getLatestSwingRanking();
  } catch {
    return (
      <div>
        <h1>Daily Swing Picks</h1>
        <p style={{ color: "#cf222e" }}>
          Couldn&apos;t reach the API. It may be waking up from sleep (free-tier cold start) — try again in
          a few seconds.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1>Daily Swing Picks</h1>
      <p style={{ display: "flex", gap: 12, alignItems: "center", color: "#57606a" }}>
        {data.scan_time && <span>Last scan: {new Date(data.scan_time).toLocaleString()}</span>}
        <RegimeBadge regime={data.regime} vix={data.vix} />
      </p>
      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
