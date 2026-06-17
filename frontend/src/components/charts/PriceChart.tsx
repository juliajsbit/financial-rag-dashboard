"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import * as d3 from "d3";
import type { PriceData, TickerInfo } from "@/types";

interface Props {
  ticker: string;
  prices: PriceData[];
  info: TickerInfo;
}

function formatPrice(v: number) {
  return d3.format("$,.2f")(v);
}

function formatMarketCap(v: number | null) {
  if (!v) return "-";
  return d3.format("$.3s")(v).replace(/G/, "B");
}

export default function PriceChart({ ticker, prices, info }: Props) {
  const first = prices[0]?.close ?? 0;
  const last = prices[prices.length - 1]?.close ?? 0;
  const change = first ? ((last - first) / first) * 100 : 0;
  const positive = change >= 0;

  const chartColor = positive ? "#22c55e" : "#ef4444";

  const domain = (() => {
    const vals = prices.map((p) => p.close);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const pad = (max - min) * 0.1;
    return [min - pad, max + pad];
  })();

  return (
    <div className="bg-panel border border-white/10 rounded-2xl p-5">
      <div className="flex items-start justify-between mb-1">
        <div>
          <span className="text-lg font-semibold text-white">{ticker}</span>
          <span className="ml-2 text-sm text-gray-500">{info.name}</span>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold text-white">
            {info.currentPrice ? formatPrice(info.currentPrice) : "-"}
          </p>
          <p
            className={`text-sm font-medium ${
              positive ? "text-green-400" : "text-red-400"
            }`}
          >
            {positive ? "+" : ""}
            {change.toFixed(2)}% (3mo)
          </p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 my-4 text-xs">
        {[
          ["Mkt Cap", formatMarketCap(info.marketCap)],
          ["P/E", info.pe ? info.pe.toFixed(1) : "-"],
          ["52w High", info.week52High ? formatPrice(info.week52High) : "-"],
          ["52w Low", info.week52Low ? formatPrice(info.week52Low) : "-"],
        ].map(([label, val]) => (
          <div key={label} className="bg-black/20 rounded-lg px-3 py-2">
            <p className="text-gray-500">{label}</p>
            <p className="text-gray-200 font-medium mt-0.5">{val}</p>
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={prices} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id={`grad-${ticker}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={chartColor} stopOpacity={0.25} />
              <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => d.slice(5)}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={domain}
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            width={50}
          />
          <Tooltip
            contentStyle={{
              background: "#161b27",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 8,
              fontSize: 12,
              color: "#e5e7eb",
            }}
            formatter={(v: number) => [formatPrice(v), "Close"]}
            labelStyle={{ color: "#6b7280" }}
          />
          <Area
            type="monotone"
            dataKey="close"
            stroke={chartColor}
            strokeWidth={2}
            fill={`url(#grad-${ticker})`}
            dot={false}
            activeDot={{ r: 4, fill: chartColor }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
