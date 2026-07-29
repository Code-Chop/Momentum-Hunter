import { getLatestIntradayWatchlist, type IntradayPick } from "@/lib/api";
import RankingTable, { type Column } from "@/components/RankingTable";
import StatTile from "@/components/StatTile";

export const dynamic = "force-dynamic";

const flag = (on: boolean) => (
  <span className={`flag ${on ? "on" : "off"}`} aria-label={on ? "yes" : "no"}>
    {on ? "●" : "○"}
  </span>
);

const signed = (v: number, suffix = "%") => (
  <span className={`delta ${v >= 0 ? "is-pos" : "is-neg"}`}>
    {v >= 0 ? "+" : ""}
    {v.toFixed(2)}
    {suffix}
  </span>
);

const columns: Column<IntradayPick>[] = [
  { key: "symbol", label: "Symbol" },
  { key: "last_close", label: "Last", numeric: true, format: (v) => `₹${Number(v).toFixed(2)}` },
  { key: "return_pct", label: "Return", numeric: true, format: (v) => signed(Number(v)) },
  { key: "volume_ratio", label: "Vol", numeric: true, format: (v) => `${Number(v).toFixed(2)}×` },
  { key: "breakout", label: "Breakout", format: (v) => flag(Boolean(v)) },
  { key: "above_vwap", label: "VWAP", format: (v) => flag(Boolean(v)) },
  {
    key: "rs_vs_nifty",
    label: "RS vs Nifty",
    numeric: true,
    format: (v) => (v === null ? <span style={{ color: "var(--ink-muted)" }}>—</span> : signed(Number(v))),
  },
  {
    key: "ai_score",
    label: "AI",
    numeric: true,
    format: (v) =>
      Number(v) > 0 ? `${Number(v).toFixed(1)}` : <span style={{ color: "var(--ink-muted)" }}>—</span>,
  },
  { key: "final_score", label: "Final score", meter: true },
];

export default async function IntradayPage() {
  let data;
  try {
    data = await getLatestIntradayWatchlist();
  } catch {
    return (
      <div>
        <div className="page-head">
          <span className="label">Intraday scan</span>
          <h1>Intraday watchlist</h1>
        </div>
        <div className="empty">
          Couldn&apos;t reach the API — free-tier instances sleep when idle and take ~30s to wake.
          Refresh in a moment.
        </div>
      </div>
    );
  }

  const breakouts = data.picks.filter((p) => p.breakout).length;
  const aboveVwap = data.picks.filter((p) => p.above_vwap).length;

  return (
    <div>
      <div className="page-head">
        <span className="label">Intraday scan · 15-minute bars</span>
        <h1>Intraday watchlist</h1>
        <p className="page-sub">
          Scored on volume surge, intraday return, VWAP position, breakout state and relative strength
          against the Nifty. Runs through market hours.
        </p>
      </div>

      <div className="tile-row">
        <StatTile label="Scored" value={String(data.picks.length)} sub="stocks" />
        <StatTile label="Breaking out" value={String(breakouts)} sub="of scored" />
        <StatTile label="Above VWAP" value={String(aboveVwap)} sub="of scored" />
        <StatTile
          label="Last scan"
          value={data.scan_time ? new Date(data.scan_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
          sub={data.scan_time ? new Date(data.scan_time).toLocaleDateString() : undefined}
        />
      </div>

      <RankingTable columns={columns} rows={data.picks} />
    </div>
  );
}
