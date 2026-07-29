const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export type SwingPick = {
  symbol: string;
  score: number;
  ai_score: number;
  final_score: number;
};

export type SwingRankingResponse = {
  scan_time: string | null;
  regime: string | null;
  vix: string | null;
  picks: SwingPick[];
};

export type IntradayPick = {
  symbol: string;
  score: number;
  volume_ratio: number;
  return_pct: number;
  breakout: boolean;
  above_vwap: boolean;
  vwap: number;
  rs_vs_nifty: number | null;
  last_close: number;
  ai_score: number;
  final_score: number;
};

export type IntradayWatchlistResponse = {
  scan_time: string | null;
  picks: IntradayPick[];
};

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return res.json();
}

export function getLatestSwingRanking() {
  return fetchJson<SwingRankingResponse>("/api/swing/latest");
}

export function getLatestIntradayWatchlist() {
  return fetchJson<IntradayWatchlistResponse>("/api/intraday/latest");
}

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  created_at: string | null;
};

export function getChatHistory() {
  return fetchJson<ChatMessage[]>("/api/chat/history");
}

export async function sendChatMessage(message: string, token?: string): Promise<ChatMessage> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["X-Chat-Token"] = token;

  const res = await fetch(`${API_BASE_URL}/api/chat/send`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    throw new Error(`Request to /api/chat/send failed with status ${res.status}`);
  }
  return res.json();
}
