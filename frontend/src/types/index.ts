export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
}

export interface Source {
  ticker: string | null;
  date: string | null;
  type: string | null;
  preview: string;
}

export interface PriceData {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
}

export interface TickerInfo {
  name: string;
  sector: string | null;
  marketCap: number | null;
  currentPrice: number | null;
  pe: number | null;
  week52High: number | null;
  week52Low: number | null;
}

export interface TickerData {
  ticker: string;
  prices: PriceData[];
  info: TickerInfo;
}
