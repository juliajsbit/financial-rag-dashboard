import type { Source, TickerData } from "@/types";

const BASE = "/api";

export async function* streamChat(
  question: string,
  tickers: string[]
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, tickers }),
  });

  if (!res.ok) throw new Error(`Stream error: ${res.status}`);
  if (!res.body) throw new Error("No response body");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (!payload) continue;
      try {
        const json = JSON.parse(payload);
        if (json.token) yield json.token;
        if (json.done) return;
        if (json.error) throw new Error(json.error);
      } catch {
        // skip malformed lines
      }
    }
  }
}

export async function fetchSources(
  question: string,
  tickers: string[]
): Promise<Source[]> {
  const res = await fetch(`${BASE}/chat/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, tickers }),
  });
  if (!res.ok) throw new Error(`Sources error: ${res.status}`);
  const data = await res.json();
  return data.sources as Source[];
}

export async function ingestTicker(
  ticker: string,
  period = "3mo"
): Promise<{ documents_stored: number }> {
  const res = await fetch(`${BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, period }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Ingest failed");
  }
  return res.json();
}

export async function fetchTickerData(
  ticker: string,
  period = "3mo"
): Promise<TickerData> {
  const res = await fetch(`${BASE}/prices/${ticker}?period=${period}`);
  if (!res.ok) throw new Error(`Price fetch error: ${res.status}`);
  return res.json();
}
