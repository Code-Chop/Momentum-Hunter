import type { ReactNode } from "react";

const PIPELINE = [
  { step: "Universe", detail: "Nifty 500 constituents with sector tags, rebuilt on demand." },
  { step: "Data sourcing", detail: "yfinance for history and fallback; Angel One SmartAPI as a real-time fast path where credentials are configured. Per-day caching keeps repeat scans cheap." },
  { step: "Momentum scoring", detail: "Weighted 1M/3M/6M returns, adjusted for 50- and 200-DMA position, volume quality, RSI band and distance from the 52-week high." },
  { step: "Regime gate", detail: "Nifty against its 200-DMA and the India VIX decide how many picks surface — and whether the scan runs defensively at all." },
  { step: "AI conviction", detail: "Top candidates plus live news headlines go to Gemini, which returns a 1–10 conviction score blended additively into the quantitative rank." },
  { step: "Diversification", detail: "A cap of two names per sector, so a hot sector can't quietly become the whole portfolio." },
  { step: "Persistence", detail: "Results are written to Postgres as the source of truth, with CSV kept as a best-effort local convenience." },
  { step: "Execution", detail: "Scans run as GitHub Actions jobs rather than on the API host — a scan takes minutes, and free-tier web instances sleep when idle and could be suspended mid-run. Triggered on demand here and from chat; a cron schedule is one config block away, left off so a demo deployment isn't spending LLM quota unattended." },
  { step: "Delivery", detail: "A Telegram alert fires directly from the scan; this dashboard and its chat read the same data." },
];

const TECH = [
  { group: "Scanning & AI", items: "Python, pandas, NumPy, yfinance, Angel One SmartAPI, Google Gemini" },
  { group: "Persistence", items: "PostgreSQL (Supabase), SQLAlchemy" },
  { group: "API", items: "FastAPI, Pydantic, Uvicorn — hosted on Render" },
  { group: "Dashboard", items: "Next.js, TypeScript, React — hosted on Vercel" },
  { group: "Automation", items: "GitHub Actions (scheduled scans), Telegram Bot API" },
];

const COMMANDS = [
  { cmd: "/top5", desc: "Top swing picks from the last scan", gated: false },
  { cmd: "/intraday", desc: "Top intraday picks from the last scan", gated: false },
  { cmd: "/status", desc: "Market regime, VIX, and last scan times", gated: false },
  { cmd: "/check", desc: "Live market pulse — Nifty, Bank Nifty, VIX, sectors", gated: false },
  { cmd: "/positions", desc: "Live P&L on tracked positions", gated: false },
  { cmd: "/decide [swing|intraday]", desc: "AI decision with entry, stop and target levels", gated: true },
  { cmd: "/add SYMBOL ENTRY [STOP TARGET]", desc: "Track a position for stop/target alerts", gated: true },
  { cmd: "/exit SYMBOL | all", desc: "Stop tracking a position", gated: true },
  { cmd: "/scan [intraday [fast]]", desc: "Run a fresh scan", gated: true },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export default function AboutPage() {
  return (
    <div>
      <div className="page-head">
        <span className="label">About</span>
        <h1>How Momentum Hunter works</h1>
        <p className="page-sub">
          An end-to-end momentum system for the Indian market: it ranks the Nifty 500 on price behaviour,
          layers an LLM conviction read on the strongest names, and publishes the result to Telegram and
          this dashboard.
        </p>
      </div>

      <Section title="The pipeline">
        <div className="steps">
          {PIPELINE.map((p) => (
            <div className="step" key={p.step}>
              <strong>{p.step}</strong>
              <span>{p.detail}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Stack">
        <div className="defs">
          {TECH.map((t) => (
            <div className="def" key={t.group}>
              <strong>{t.group}</strong>
              <span>{t.items}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Commands">
        <p className="prose" style={{ fontSize: 13.5, marginTop: 0, marginBottom: 13 }}>
          The same command layer drives both the Telegram bot and the{" "}
          <a href="/chat">web chat</a>. Reads are open to anyone; commands that write real positions or
          spend LLM quota need an access code.
        </p>
        <div className="cmds">
          {COMMANDS.map((c) => (
            <div className="cmd" key={c.cmd}>
              <code>
                {c.cmd}
                {c.gated && <span style={{ color: "var(--ink-muted)" }}> ·&nbsp;locked</span>}
              </code>
              <span>{c.desc}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Known limits">
        <p className="note">
          Free-tier hosting sleeps when idle, so a first visit after a quiet spell takes about half a
          minute to wake. Angel One stays disabled in the cloud — its session tokens don&apos;t survive an
          ephemeral runner — so hosted scans use yfinance throughout, which is rate-limited more
          aggressively from datacenter IPs than from home connections. Backtest figures come from a single
          historical window and have not been walk-forward validated.
        </p>
      </Section>

      <Section title="Disclaimer">
        <p className="note">
          This is an educational and research project. It is not financial advice and makes no guarantee of
          returns. Trading equities carries risk of loss — validate everything independently before risking
          real capital.
        </p>
      </Section>
    </div>
  );
}
