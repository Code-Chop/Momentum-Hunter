import Link from "next/link";
import { getLatestSwingRanking } from "@/lib/api";
import RegimeBadge from "@/components/RegimeBadge";

export const dynamic = "force-dynamic";

const PILLARS = [
  {
    title: "Multi-timeframe momentum",
    body: "1M, 3M and 6M returns weighted against 200-DMA, volume quality, RSI and distance from the 52-week high — across the full Nifty 500.",
  },
  {
    title: "An LLM conviction layer",
    body: "The strongest candidates go to Gemini with live news context and come back scored 1–10, blended into the quantitative rank rather than replacing it.",
  },
  {
    title: "Regime-aware scoring",
    body: "Weights shift with the market: Nifty against its 200-DMA and the India VIX decide how many picks surface, and how defensively.",
  },
  {
    title: "Runs itself, for free",
    body: "Scheduled scans on GitHub Actions write to Postgres; a FastAPI service and this dashboard serve it. Every tier is free.",
  },
];

const STACK = [
  "Python", "pandas", "FastAPI", "PostgreSQL", "SQLAlchemy",
  "Next.js", "TypeScript", "Gemini", "GitHub Actions", "Telegram Bot API",
];

async function ProofPanel() {
  let data;
  try {
    data = await getLatestSwingRanking();
  } catch {
    return (
      <div className="card proof">
        <div className="proof-head">
          <span className="label">Latest swing picks</span>
        </div>
        <p style={{ padding: "18px 4px", margin: 0, color: "var(--ink-muted)", fontSize: 13 }}>
          Waking the API — free-tier instances sleep when idle. Refresh in a moment.
        </p>
      </div>
    );
  }

  const top = data.picks.slice(0, 5);

  return (
    <div className="card proof">
      <div className="proof-head">
        <span className="label">Latest swing picks</span>
        <RegimeBadge regime={data.regime} vix={data.vix} />
      </div>

      {top.length === 0 ? (
        <p style={{ padding: "18px 4px", margin: 0, color: "var(--ink-muted)", fontSize: 13 }}>
          No picks in the last scan.
        </p>
      ) : (
        top.map((p, i) => (
          <div className="proof-row" key={p.symbol}>
            <span className="proof-rank">{i + 1}</span>
            <span>
              <span className="proof-sym">{p.symbol}</span>
              {p.ai_score > 0 && <span className="proof-ai">AI {p.ai_score.toFixed(1)}/10</span>}
            </span>
            <span className="proof-score">{p.final_score.toFixed(1)}</span>
          </div>
        ))
      )}

      {data.scan_time && (
        <div style={{ paddingTop: 11, marginTop: 4, borderTop: "1px solid var(--rule)" }}>
          <span className="tile-sub num">
            Scanned {new Date(data.scan_time).toLocaleString()}
          </span>
        </div>
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <div>
      <section className="hero">
        <div className="hero-grid">
          <div>
            <span className="label">NSE · Nifty 500 · quantitative + LLM</span>
            <h1 style={{ marginTop: 10 }}>
              A momentum scanner that ranks 500 stocks, then argues with itself.
            </h1>
            <p>
              Momentum Hunter scores the entire Nifty 500 on multi-timeframe price behaviour, sends the
              strongest names to an LLM for a conviction read against live news, and publishes the blended
              ranking here and to Telegram — on a schedule, with no server to keep alive.
            </p>
            <div className="hero-actions">
              <Link href="/swing" className="btn btn-primary">View swing picks</Link>
              <Link href="/intraday" className="btn btn-ghost">Intraday watchlist</Link>
              <Link href="/about" className="btn btn-ghost">How it works</Link>
            </div>
          </div>

          <ProofPanel />
        </div>
      </section>

      <section className="strip">
        {PILLARS.map((p) => (
          <div className="strip-cell" key={p.title}>
            <h3>{p.title}</h3>
            <p>{p.body}</p>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 34 }}>
        <span className="label">Built with</span>
        <div className="stack-list">
          {STACK.map((s) => (
            <span className="stack-item" key={s}>{s}</span>
          ))}
        </div>
      </section>
    </div>
  );
}
