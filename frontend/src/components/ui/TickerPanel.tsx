"use client";

import { useState } from "react";
import { ingestTicker } from "@/lib/api";

interface Props {
  tickers: string[];
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

export default function TickerPanel({ tickers, onAdd, onRemove }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd() {
    const t = input.trim().toUpperCase();
    if (!t || tickers.includes(t)) return;
    setLoading(t);
    setError(null);
    try {
      await ingestTicker(t);
      onAdd(t);
      setInput("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ticker");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="bg-panel border border-white/10 rounded-2xl p-5">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
        Tickers
      </h2>

      <div className="flex gap-2 mb-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          placeholder="e.g. NVDA"
          className="flex-1 bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand"
        />
        <button
          onClick={handleAdd}
          disabled={!!loading || !input.trim()}
          className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-50 hover:bg-brand/80 transition-colors"
        >
          {loading ? "Loading..." : "Add"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400 mb-3">{error}</p>
      )}

      <div className="space-y-2">
        {tickers.length === 0 && (
          <p className="text-xs text-gray-600">No tickers added yet.</p>
        )}
        {tickers.map((t) => (
          <div
            key={t}
            className="flex items-center justify-between bg-black/20 rounded-lg px-3 py-2"
          >
            <span className="text-sm font-medium text-brand-light">{t}</span>
            <button
              onClick={() => onRemove(t)}
              className="text-gray-600 hover:text-red-400 text-xs transition-colors"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
