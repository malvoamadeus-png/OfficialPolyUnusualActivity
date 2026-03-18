"use client";

import { useState } from "react";
import { WhaleTrade } from "@/lib/types";

// ln bar: $10k → 0%, $1M → 100%, cap at 100%
const LN_MIN = Math.log(10_000);
const LN_MAX = Math.log(1_000_000);

function sizeBarPercent(size: number): number {
  if (size >= 1_000_000) return 100;
  if (size <= 10_000) return 2;
  return ((Math.log(size) - LN_MIN) / (LN_MAX - LN_MIN)) * 100;
}

function formatUsd(n: number): string {
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

const VALUE_FILTERS = [0, 10000, 20000, 30000, 40000, 50000, 60000, 70000, 80000, 90000, 100000];
const FILTER_LABELS: Record<number, string> = {
  0: "全部", 10000: "≥$1万", 20000: "≥$2万", 30000: "≥$3万",
  40000: "≥$4万", 50000: "≥$5万", 60000: "≥$6万", 70000: "≥$7万",
  80000: "≥$8万", 90000: "≥$9万", 100000: "≥$10万",
};

type Tab = "normal" | "endgame";

export function WhaleTradeList({ trades }: { trades: WhaleTrade[] }) {
  const [tab, setTab] = useState<Tab>("normal");
  const [minValue, setMinValue] = useState(0);

  const normal = trades.filter((t) => t.price <= 0.95);
  const endgame = trades.filter((t) => t.price > 0.95);
  const current = tab === "normal" ? normal : endgame;
  const filtered = minValue > 0
    ? current.filter((t) => t.size * t.price >= minValue)
    : current;

  return (
    <div>
      {/* 二级导航 */}
      <div className="mb-3 flex items-center gap-4">
        {(["normal", "endgame"] as Tab[]).map((k) => {
          const label = k === "normal" ? "正常" : "尾盘";
          const count = k === "normal" ? normal.length : endgame.length;
          const active = tab === k;
          return (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                active
                  ? "bg-[#30363d] text-[#e1e4e8]"
                  : "text-[#8b949e] hover:text-[#e1e4e8]"
              }`}
            >
              {label}
              <span className="ml-1 text-xs text-[#6e7681]">{count}</span>
            </button>
          );
        })}

        {/* 美元价值筛选 */}
        <select
          value={minValue}
          onChange={(e) => setMinValue(Number(e.target.value))}
          className="ml-auto rounded-md border border-[#30363d] bg-[#0d1117] px-2 py-1 text-xs text-[#e1e4e8]"
        >
          {VALUE_FILTERS.map((v) => (
            <option key={v} value={v}>{FILTER_LABELS[v]}</option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {filtered.map((t) => (
            <TradeRow key={t.transaction_hash} t={t} />
          ))}
        </div>
      )}
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
  const usdValue = t.size * t.price;

  // 配色: ≥$100k 金色, ≥$50k 紫色, 其余默认
  let rowBorder = "border-[#30363d]";
  let rowBg = "bg-[#161b22]";
  if (usdValue >= 100_000) {
    rowBorder = "border-[#d4a72c]/50";
    rowBg = "bg-[#d4a72c]/5";
  } else if (usdValue >= 50_000) {
    rowBorder = "border-[#a371f7]/40";
    rowBg = "bg-[#a371f7]/5";
  }

  return (
    <div className={`flex items-center gap-3 rounded-lg border ${rowBorder} ${rowBg} px-3.5 py-2.5 text-sm`}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <a href={profileUrl} target="_blank" rel="noopener noreferrer"
            className="shrink-0 font-semibold text-[#58a6ff] hover:underline">
            {displayName}
          </a>
          <span className={`shrink-0 text-xs font-bold ${sideColor}`}>{t.side}</span>
          <span className="shrink-0 text-xs text-[#6e7681]">{t.outcome}</span>
        </div>
        <p className="mt-0.5 truncate text-xs text-[#8b949e]">{t.title}</p>
      </div>

      <div className="shrink-0 text-right text-xs">
        <span className="text-[#e1e4e8]">{(t.price * 100).toFixed(1)}¢</span>
      </div>

      {/* Size bar + size */}
      <div className="w-[180px] shrink-0">
        <div className="flex items-center gap-2">
          <div className="h-4 flex-1 overflow-hidden rounded-sm bg-[#21262d]">
            <div className={`h-full rounded-sm ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="w-[60px] text-right text-xs font-medium text-[#e1e4e8]">
            {formatUsd(t.size)}
          </span>
        </div>
      </div>

      {/* USD value */}
      <span className={`w-[60px] shrink-0 text-right text-xs font-medium ${
        usdValue >= 100_000 ? "text-[#d4a72c]" : usdValue >= 50_000 ? "text-[#a371f7]" : "text-[#8b949e]"
      }`}>
        {formatUsd(usdValue)}
      </span>

      <span className="w-[32px] shrink-0 text-right text-xs text-[#6e7681]">
        {timeAgo(t.timestamp)}
      </span>
    </div>
  );
}
