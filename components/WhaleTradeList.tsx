"use client";

import { WhaleTrade } from "@/lib/types";

// ln bar: $10k → 0%, $1M → 100%, cap at 100%
const LN_MIN = Math.log(10_000);
const LN_MAX = Math.log(1_000_000);

function sizeBarPercent(size: number): number {
  if (size >= 1_000_000) return 100;
  if (size <= 10_000) return 2;
  return ((Math.log(size) - LN_MIN) / (LN_MAX - LN_MIN)) * 100;
}

function formatSize(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000) - ts;
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

export function WhaleTradeList({ trades }: { trades: WhaleTrade[] }) {
  if (trades.length === 0) {
    return <p className="py-10 text-center text-[#8b949e]">暂无数据</p>;
  }

  return (
    <div className="flex flex-col gap-1.5">
      {trades.map((t) => (
        <TradeRow key={t.transaction_hash} t={t} />
      ))}
    </div>
  );
}

function TradeRow({ t }: { t: WhaleTrade }) {
  const isBuy = t.side === "BUY";
  const barColor = isBuy ? "bg-[#238636]" : "bg-[#da3633]";
  const sideColor = isBuy ? "text-[#3fb950]" : "text-[#f85149]";
  const pct = sizeBarPercent(t.size);
  const displayName = t.name || t.proxy_wallet.slice(0, 8) + "...";
  const profileUrl = `https://polymarket.com/profile/${t.proxy_wallet}?tab=activity`;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-[#30363d] bg-[#161b22] px-3.5 py-2.5 text-sm">
      {/* Left: name + title */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <a
            href={profileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 font-semibold text-[#58a6ff] hover:underline"
          >
            {displayName}
          </a>
          <span className={`shrink-0 text-xs font-bold ${sideColor}`}>
            {t.side}
          </span>
          <span className="shrink-0 text-xs text-[#6e7681]">
            {t.outcome}
          </span>
        </div>
        <p className="mt-0.5 truncate text-xs text-[#8b949e]">{t.title}</p>
      </div>

      {/* Price */}
      <div className="shrink-0 text-right text-xs">
        <span className="text-[#e1e4e8]">{(t.price * 100).toFixed(1)}¢</span>
      </div>

      {/* Size bar */}
      <div className="w-[180px] shrink-0">
        <div className="flex items-center gap-2">
          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-[#21262d]">
            <div
              className={`h-full rounded-sm ${barColor}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="w-[60px] text-right text-xs font-medium text-[#e1e4e8]">
            {formatSize(t.size)}
          </span>
        </div>
      </div>

      {/* Time */}
      <span className="w-[32px] shrink-0 text-right text-xs text-[#6e7681]">
        {timeAgo(t.timestamp)}
      </span>
    </div>
  );
}
