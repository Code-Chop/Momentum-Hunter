import Link from "next/link";

export default function HomePage() {
  return (
    <div>
      <h1>Momentum Hunter</h1>
      <p>AI-enhanced NSE momentum scanner. Choose a view:</p>
      <ul>
        <li>
          <Link href="/swing">Daily Swing Picks</Link>
        </li>
        <li>
          <Link href="/intraday">Intraday Watchlist</Link>
        </li>
      </ul>
    </div>
  );
}
