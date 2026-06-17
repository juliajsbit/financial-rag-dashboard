"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import PriceChart from "@/components/charts/PriceChart";
import TickerPanel from "@/components/ui/TickerPanel";
import { streamChat, fetchSources, fetchTickerData } from "@/lib/api";
import type { Message, TickerData } from "@/types";

let msgCounter = 0;
function uid() {
  return `msg-${++msgCounter}`;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [tickers, setTickers] = useState<string[]>([]);
  const [tickerData, setTickerData] = useState<Record<string, TickerData>>({});
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadTickerData = useCallback(async (ticker: string) => {
    try {
      const data = await fetchTickerData(ticker);
      setTickerData((prev) => ({ ...prev, [ticker]: data }));
    } catch {
      // silently ignore chart fetch failures
    }
  }, []);

  function addTicker(ticker: string) {
    setTickers((prev) => [...prev, ticker]);
    loadTickerData(ticker);
  }

  function removeTicker(ticker: string) {
    setTickers((prev) => prev.filter((t) => t !== ticker));
    setTickerData((prev) => {
      const next = { ...prev };
      delete next[ticker];
      return next;
    });
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || isSending) return;

    setInput("");
    setIsSending(true);

    const userMsg: Message = { id: uid(), role: "user", content: text };
    const assistantId = uid();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      // Stream the answer
      let accumulated = "";
      for await (const token of streamChat(text, tickers)) {
        accumulated += token;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: accumulated } : m
          )
        );
      }

      // Fetch sources after streaming
      const sources = await fetchSources(text, tickers).catch(() => []);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, sources, streaming: false } : m
        )
      );
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "Unknown error";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: `Error: ${errMsg}`, streaming: false }
            : m
        )
      );
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-white">
      {/* Left sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-white/10 flex flex-col p-4 gap-4 overflow-y-auto">
        <div className="flex items-center gap-2 py-2">
          <div className="w-7 h-7 rounded-lg bg-brand flex items-center justify-center text-xs font-bold">
            F
          </div>
          <span className="font-semibold text-sm">FinRAG</span>
        </div>

        <TickerPanel tickers={tickers} onAdd={addTicker} onRemove={removeTicker} />
      </aside>

      {/* Main area */}
      <main className="flex flex-1 flex-col min-w-0">
        {/* Charts row */}
        {tickers.length > 0 && (
          <div className="flex-shrink-0 border-b border-white/10 p-4 overflow-x-auto">
            <div className="flex gap-4" style={{ minWidth: `${tickers.length * 380}px` }}>
              {tickers.map((t) =>
                tickerData[t] ? (
                  <div key={t} className="w-[360px] flex-shrink-0">
                    <PriceChart
                      ticker={t}
                      prices={tickerData[t].prices}
                      info={tickerData[t].info}
                    />
                  </div>
                ) : (
                  <div
                    key={t}
                    className="w-[360px] flex-shrink-0 bg-panel border border-white/10 rounded-2xl p-5 flex items-center justify-center"
                  >
                    <p className="text-sm text-gray-600 animate-pulse">
                      Loading {t}...
                    </p>
                  </div>
                )
              )}
            </div>
          </div>
        )}

        {/* Chat */}
        <div className="flex-1 overflow-y-auto p-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-3 text-gray-600">
              <p className="text-3xl">📊</p>
              <p className="text-sm">
                Add a ticker on the left, then ask anything about it.
              </p>
              <p className="text-xs text-gray-700">
                Try: "What happened to NVDA this quarter?"
              </p>
            </div>
          )}
          {messages.map((m) => (
            <ChatMessage key={m.id} message={m} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex-shrink-0 border-t border-white/10 p-4">
          <div className="flex gap-3 max-w-3xl mx-auto">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about your tickers..."
              className="flex-1 bg-panel border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand"
            />
            <button
              onClick={sendMessage}
              disabled={isSending || !input.trim()}
              className="px-5 py-3 rounded-xl bg-brand text-white text-sm font-medium disabled:opacity-50 hover:bg-brand/80 transition-colors"
            >
              {isSending ? "..." : "Send"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
