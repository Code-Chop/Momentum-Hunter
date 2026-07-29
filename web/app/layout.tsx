import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Momentum Hunter",
  description: "AI-enhanced NSE momentum scanner — swing and intraday picks",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          color: "#1f2328",
          backgroundColor: "#fff",
        }}
      >
        <header
          style={{
            borderBottom: "1px solid #d0d7de",
            padding: "16px 24px",
            display: "flex",
            alignItems: "center",
            gap: 24,
          }}
        >
          <strong style={{ fontSize: 18 }}>Momentum Hunter</strong>
          <nav style={{ display: "flex", gap: 16 }}>
            <Link href="/swing">Swing Picks</Link>
            <Link href="/intraday">Intraday Watchlist</Link>
          </nav>
        </header>
        <main style={{ padding: 24, maxWidth: 960, margin: "0 auto" }}>{children}</main>
      </body>
    </html>
  );
}
