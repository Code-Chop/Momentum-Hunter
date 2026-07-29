import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Momentum Hunter",
  description: "AI-enhanced NSE momentum scanner — swing and intraday picks, live dashboard",
};

const GITHUB_URL = "https://github.com/Code-Chop/Momentum-Hunter";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header
          style={{
            borderBottom: "1px solid var(--border)",
            background: "var(--surface-1)",
            position: "sticky",
            top: 0,
            zIndex: 10,
          }}
        >
          <div
            style={{
              maxWidth: 1080,
              margin: "0 auto",
              padding: "14px 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 24,
            }}
          >
            <Link href="/" style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}>
              <span style={{ fontSize: 20 }}>📈</span>
              <strong style={{ fontSize: 17, color: "var(--text-primary)" }}>Momentum Hunter</strong>
            </Link>
            <nav style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 14 }}>
              <Link href="/swing" style={{ color: "var(--text-secondary)" }}>
                Swing Picks
              </Link>
              <Link href="/intraday" style={{ color: "var(--text-secondary)" }}>
                Intraday
              </Link>
              <Link href="/chat" style={{ color: "var(--text-secondary)" }}>
                Chat
              </Link>
              <Link href="/about" style={{ color: "var(--text-secondary)" }}>
                About
              </Link>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: "var(--text-primary)",
                  border: "1px solid var(--border)",
                  borderRadius: 6,
                  padding: "6px 12px",
                  textDecoration: "none",
                  fontWeight: 600,
                }}
              >
                GitHub ↗
              </a>
            </nav>
          </div>
        </header>

        <main style={{ maxWidth: 1080, margin: "0 auto", padding: "32px 24px", minHeight: "70vh" }}>
          {children}
        </main>

        <footer
          style={{
            borderTop: "1px solid var(--border)",
            padding: "24px",
            marginTop: 40,
            textAlign: "center",
            color: "var(--text-muted)",
            fontSize: 13,
          }}
        >
          Educational / research project — not financial advice. ·{" "}
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer" style={{ color: "var(--text-muted)" }}>
            Source on GitHub
          </a>
        </footer>
      </body>
    </html>
  );
}
