"use client";

import { useEffect, useRef, useState } from "react";
import { getChatHistory, sendChatMessage, type ChatMessage } from "@/lib/api";

const SUGGESTIONS = ["/top5", "/intraday", "/status", "/check", "/positions", "/decide", "/scan", "/help"];
const GATED_PREFIXES = ["/scan", "/decide"];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refresh = async () => {
    try {
      const history = await getChatHistory();
      setMessages(history);
      setError(null);
    } catch {
      setError("Couldn't reach the API — it may be waking up from sleep. Retrying...");
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    let token: string | undefined = localStorage.getItem("mh_chat_token") ?? undefined;
    const isGated = GATED_PREFIXES.some((p) => trimmed.toLowerCase().startsWith(p));
    if (isGated && !token) {
      const entered = window.prompt("Enter the access code for this command:");
      if (entered) {
        token = entered;
        localStorage.setItem("mh_chat_token", entered);
      }
    }

    setSending(true);
    setInput("");
    setMessages((m) => [...m, { role: "user", content: trimmed, created_at: null }]);
    try {
      const reply = await sendChatMessage(trimmed, token);
      setMessages((m) => [...m, reply]);
    } catch {
      setError("Couldn't send — check the API is running.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 4 }}>Chat</h1>
      <p style={{ color: "var(--text-secondary)", fontSize: 13.5, marginBottom: 20 }}>
        Same engine as the Telegram bot — run scans, check status, and pull picks from here.
      </p>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => handleSend(s)}
            disabled={sending}
            style={{
              fontSize: 12.5,
              padding: "5px 12px",
              borderRadius: 999,
              border: "1px solid var(--border)",
              background: "var(--surface-1)",
              color: "var(--text-secondary)",
              cursor: "pointer",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div
        style={{
          border: "1px solid var(--border)",
          borderRadius: 10,
          background: "var(--surface-1)",
          height: 440,
          overflowY: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: 13.5, margin: "auto" }}>
            No messages yet — try one of the commands above.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "80%",
              background: m.role === "user" ? "var(--seq-500)" : "var(--surface-2)",
              color: m.role === "user" ? "#fff" : "var(--text-primary)",
              padding: "8px 12px",
              borderRadius: 10,
              fontSize: 14,
              whiteSpace: "pre-wrap",
            }}
          >
            {m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p style={{ color: "var(--status-critical)", fontSize: 12.5, marginTop: 8 }}>{error}</p>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        style={{ display: "flex", gap: 8, marginTop: 12 }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a command, e.g. /top5"
          style={{
            flex: 1,
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--surface-1)",
            color: "var(--text-primary)",
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          disabled={sending}
          style={{
            padding: "10px 18px",
            borderRadius: 8,
            border: "none",
            background: "var(--seq-500)",
            color: "#fff",
            fontWeight: 600,
            cursor: sending ? "default" : "pointer",
          }}
        >
          {sending ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
