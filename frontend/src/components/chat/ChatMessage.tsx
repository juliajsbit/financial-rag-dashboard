"use client";

import type { Message } from "@/types";

interface Props {
  message: Message;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-brand text-white"
            : "bg-panel border border-white/10 text-gray-200"
        }`}
      >
        <p className="whitespace-pre-wrap">
          {message.content}
          {message.streaming && (
            <span className="inline-block w-1.5 h-4 bg-brand-light ml-0.5 animate-pulse align-text-bottom" />
          )}
        </p>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/10 space-y-1.5">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Sources
            </p>
            {message.sources.map((src, i) => (
              <div
                key={i}
                className="text-xs text-gray-400 bg-black/20 rounded-lg px-3 py-2"
              >
                <span className="text-brand-light font-medium">
                  {src.ticker ?? "-"}
                </span>
                {src.date && (
                  <span className="text-gray-500 ml-2">{src.date.slice(0, 10)}</span>
                )}
                {src.type && (
                  <span className="ml-2 text-gray-600 italic">{src.type}</span>
                )}
                <p className="mt-1 text-gray-500 line-clamp-2">{src.preview}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
