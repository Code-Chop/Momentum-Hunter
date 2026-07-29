const PIPELINE = [
  { step: "1. Universe", detail: "Nifty 500 constituents with sector tags (build_universe.py)." },
  { step: "2. Data sourcing", detail: "yfinance (historical/fallback) + Angel One SmartAPI (real-time, local deployments) with per-day caching." },
  { step: "3. Scoring", detail: "Momentum (1M/3M/6M returns, DMA, RSI, volume) for swing; VWAP/breakout/RS for intraday." },
  { step: "4. AI conviction", detail: "Top candidates + live news sent to Gemini, returns a 1-10 conviction score blended with the quant score." },
  { step: "5. Diversification", detail: "Sector cap (max 2 per sector) applied to the final ranked picks." },
  { step: "6. Persistence", detail: "Written to Postgres (Supabase) as the source of truth, with CSV as a local-dev fallback." },
  { step: "7. Scheduling", detail: "GitHub Actions cron runs the swing scan after close and the intraday scan every ~30 min in market hours." },
  { step: "8. Delivery", detail: "Telegram alert sent directly + this dashboard (FastAPI read API on Render, Next.js on Vercel)." },
];

const TELEGRAM_COMMANDS = [
  { cmd: "/scan", desc: "Run a swing scan in the background" },
  { cmd: "/scan intraday [fast]", desc: "Run a full or fast intraday scan" },
  { cmd: "/decide [swing|intraday]", desc: "AI decision: live market + picks → entry / stop / target" },
  { cmd: "/check", desc: "Instant market pulse (NIFTY, BankNifty, VIX, sectors)" },
  { cmd: "/top5 · /intraday", desc: "Top picks from the last swing / intraday scan" },
  { cmd: "/add SYMBOL ENTRY [STOP TARGET]", desc: "Track a live position for alerts" },
  { cmd: "/positions", desc: "Live P&L for all tracked positions" },
  { cmd: "/exit SYMBOL · /exit all", desc: "Stop tracking a position" },
  { cmd: "/status", desc: "Market regime, VIX, last scan times" },
  { cmd: "/performance · /liveperf", desc: "Backtest stats / live trade record" },
];

const TECH_STACK = [
  { group: "Scanning & AI", items: "Python, pandas, NumPy, yfinance, Angel One SmartAPI, Google Gemini" },
  { group: "Persistence", items: "PostgreSQL (Supabase), SQLAlchemy" },
  { group: "API", items: "FastAPI, Pydantic, Uvicorn (Render)" },
  { group: "Dashboard", items: "Next.js, TypeScript, React (Vercel)" },
  { group: "Automation", items: "GitHub Actions (cron), Telegram Bot API" },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 36 }}>
      <h2 style={{ fontSize: 20, marginBottom: 14 }}>{title}</h2>
      {children}
    </section>
  );
}

export default function AboutPage() {
  return (
    <div>
      <h1 style={{ marginBottom: 8 }}>About Momentum Hunter</h1>
      <p style={{ color: "var(--text-secondary)", lineHeight: 1.6, maxWidth: 680, marginBottom: 36 }}>
        An end-to-end algorithmic equity-momentum system for the Indian market (NSE). It scans the full
        Nifty 500, ranks stocks on multi-timeframe momentum, adds an LLM conviction layer, and delivers
        picks with entry/stop/target levels via Telegram and this dashboard. It also tracks live positions,
        evaluates paper trades, and backtests the strategy over historical data.
      </p>

      <Section title="How it works">
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {PIPELINE.map((p) => (
            <div
              key={p.step}
              style={{
                display: "grid",
                gridTemplateColumns: "160px 1fr",
                gap: 16,
                padding: "10px 14px",
                border: "1px solid var(--border)",
                borderRadius: 8,
                background: "var(--surface-1)",
              }}
            >
              <strong style={{ fontSize: 13.5 }}>{p.step}</strong>
              <span style={{ fontSize: 13.5, color: "var(--text-secondary)" }}>{p.detail}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Tech stack">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {TECH_STACK.map((t) => (
            <div key={t.group} style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 16, fontSize: 13.5 }}>
              <strong>{t.group}</strong>
              <span style={{ color: "var(--text-secondary)" }}>{t.items}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Telegram bot commands">
        <p style={{ fontSize: 13.5, color: "var(--text-secondary)", marginBottom: 14 }}>
          Beyond this read-only dashboard, a fully interactive Telegram bot drives the same underlying
          engine — run scans on demand, get AI trade decisions, and track live positions from chat.
        </p>
        <div style={{ border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
          {TELEGRAM_COMMANDS.map((c, i) => (
            <div
              key={c.cmd}
              style={{
                display: "grid",
                gridTemplateColumns: "230px 1fr",
                gap: 16,
                padding: "9px 14px",
                fontSize: 13.5,
                background: i % 2 === 0 ? "var(--surface-1)" : "var(--surface-2)",
              }}
            >
              <code style={{ fontFamily: "ui-monospace, monospace" }}>{c.cmd}</code>
              <span style={{ color: "var(--text-secondary)" }}>{c.desc}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Disclaimer">
        <p style={{ fontSize: 13.5, color: "var(--text-muted)", lineHeight: 1.6 }}>
          This project is for educational and research purposes only. It is not financial advice and makes
          no guarantee of returns. Trading equities carries risk of loss. Use at your own risk, and validate
          everything independently before risking real capital.
        </p>
      </Section>
    </div>
  );
}
