"use client";

import { useEffect, useRef, useState } from "react";
import { getChatHistory, sendChatMessage, type ChatMessage } from "@/lib/api";

const SUGGESTIONS = ["/top5", "/intraday", "/status", "/check", "/positions", "/decide", "/scan", "/help"];
const GATED_PREFIXES = ["/scan", "/decide", "/add", "/exit"];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const refresh = async () => {
    try {
      setMessages(await getChatHistory());
      setError(null);
    } catch {
      setError("Couldn't reach the API — free-tier instances sleep when idle. Retrying…");
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
    if (GATED_PREFIXES.some((p) => trimmed.toLowerCase().startsWith(p)) && !token) {
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
      setError("Couldn't send that — check the API is reachable.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-wrap">
      <div className="page-head">
        <span className="label">Command interface</span>
        <h1>Chat</h1>
        <p className="page-sub">
          The same engine behind the Telegram bot. Reads are open; running a scan or an AI decision needs
          an access code. Your conversation stays in this browser.
        </p>
      </div>

      <div className="chip-row">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => handleSend(s)} disabled={sending}>
            {s}
          </button>
        ))}
      </div>

      <div className="chat-log">
        {messages.length === 0 && (
          <p className="chat-empty">
            No messages yet — pick a command above, or type one below.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role === "user" ? "from-user" : "from-bot"}`}>
            {m.content}
          </div>
        ))}
        {sending && <div className="bubble from-bot dots">working</div>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="err">{error}</p>}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
      >
        <input
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a command, e.g. /top5"
          maxLength={500}
          aria-label="Command input"
        />
        <button type="submit" className="btn btn-primary" disabled={sending}>
          {sending ? "Sending" : "Send"}
        </button>
      </form>
    </div>
  );
}
