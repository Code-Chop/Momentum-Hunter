import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Momentum Hunter — NSE momentum scanner",
  description:
    "An AI-enhanced momentum scanner for the Indian market: multi-timeframe scoring across the Nifty 500, an LLM conviction layer, and a live dashboard.",
};

const GITHUB_URL = "https://github.com/Code-Chop/Momentum-Hunter";

/* A rising step-chart mark — the subject drawn, rather than a stock emoji. */
function Mark() {
  return (
    <svg className="brand-mark" viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path
        d="M2 15.5L6.4 11.1L9.6 14.3L17.5 6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12.8 6H17.5V10.7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="shell header-row">
            <Link href="/" className="brand">
              <Mark />
              <span>Momentum Hunter</span>
            </Link>
            <nav className="nav">
              <Link href="/swing" className="nav-link">Swing</Link>
              <Link href="/intraday" className="nav-link">Intraday</Link>
              <Link href="/chat" className="nav-link">Chat</Link>
              <Link href="/about" className="nav-link">About</Link>
              <span className="nav-sep" aria-hidden="true" />
              <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" className="nav-link">
                GitHub ↗
              </a>
            </nav>
          </div>
        </header>

        <main className="site-main">
          <div className="shell">{children}</div>
        </main>

        <footer className="site-footer">
          <div className="shell footer-row">
            <span>Educational and research project — not financial advice.</span>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              Source on GitHub ↗
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
