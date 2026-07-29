import Link from "next/link";

const HIGHLIGHTS = [
  {
    title: "Multi-timeframe momentum",
    body: "Scans ~500 NSE stocks on 1M/3M/6M returns, 200-DMA, volume, RSI, and 52-week-high filters.",
  },
  {
    title: "LLM conviction layer",
    body: "Top candidates get a 1-10 conviction score from Gemini, using price metrics and live news headlines.",
  },
  {
    title: "Market-regime awareness",
    body: "Scoring weights adapt to Nifty vs 200-DMA and India VIX — bull, bear, and high-VIX regimes.",
  },
  {
    title: "Intraday engine",
    body: "15-minute bar scanning for volume, VWAP, breakout, and relative strength vs Nifty.",
  },
  {
    title: "Interactive Telegram bot",
    body: "Trigger scans, get AI decisions, and track live positions with stop/target alerts from chat.",
  },
  {
    title: "Free-hosted pipeline",
    body: "GitHub Actions cron + Postgres (Supabase) + FastAPI + this dashboard — $0 infrastructure cost.",
  },
];

const TECH = [
  "Python", "FastAPI", "PostgreSQL", "Next.js", "TypeScript",
  "Google Gemini", "GitHub Actions", "Telegram Bot API",
];

export default function HomePage() {
  return (
    <div>
      <section style={{ textAlign: "center", padding: "24px 0 48px" }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>📈</div>
        <h1 style={{ fontSize: 34, margin: "0 0 12px" }}>Momentum Hunter</h1>
        <p
          style={{
            fontSize: 17,
            color: "var(--text-secondary)",
            maxWidth: 620,
            margin: "0 auto 28px",
            lineHeight: 1.6,
          }}
        >
          An end-to-end algorithmic equity-momentum system for the Indian market (NSE) — multi-timeframe
          momentum scoring, an LLM conviction layer, and a fully free-hosted pipeline from scan to dashboard.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link
            href="/swing"
            style={{
              background: "var(--seq-500)",
              color: "#fff",
              padding: "10px 20px",
              borderRadius: 8,
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            View Swing Picks
          </Link>
          <Link
            href="/intraday"
            style={{
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
              padding: "10px 20px",
              borderRadius: 8,
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            View Intraday Watchlist
          </Link>
          <Link
            href="/about"
            style={{
              color: "var(--text-secondary)",
              padding: "10px 20px",
              textDecoration: "none",
              fontWeight: 600,
            }}
          >
            How it works →
          </Link>
        </div>
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 16,
        }}
      >
        {HIGHLIGHTS.map((h) => (
          <div
            key={h.title}
            style={{
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: 18,
              background: "var(--surface-1)",
            }}
          >
            <h3 style={{ fontSize: 15, margin: "0 0 8px" }}>{h.title}</h3>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: 0, lineHeight: 1.5 }}>
              {h.body}
            </p>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 40, textAlign: "center" }}>
        <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 10 }}>
          Built with
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
          {TECH.map((t) => (
            <span
              key={t}
              style={{
                fontSize: 12.5,
                padding: "5px 12px",
                borderRadius: 999,
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
