"use client";

import { useState } from "react";
import {
  WorldCupBoardLine,
  WorldCupHolder,
  WorldCupMatchBoard,
} from "@/lib/types";

const GROUPS = [
  { key: "moneyline", label: "Moneyline" },
  { key: "spread", label: "让分" },
  { key: "total", label: "总分" },
] as const;

function lineKey(eventSlug: string, boardType: string, line: WorldCupBoardLine): string {
  return `${eventSlug}:${boardType}:${line.condition_id || line.market_slug || line.label}`;
}

export function WorldCupBoard({ matches }: { matches: WorldCupMatchBoard[] }) {
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
  const [expandedLines, setExpandedLines] = useState<Set<string>>(new Set());

  function toggleEvent(eventSlug: string) {
    setExpandedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(eventSlug)) {
        next.delete(eventSlug);
      } else {
        next.add(eventSlug);
      }
      return next;
    });
  }

  function toggleLine(key: string) {
    setExpandedLines((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function expandAll() {
    const nextEvents = new Set(matches.map((match) => match.event_slug));
    const nextLines = new Set<string>();
    for (const match of matches) {
      for (const group of GROUPS) {
        for (const line of match.boards_json[group.key]) {
          nextLines.add(lineKey(match.event_slug, group.key, line));
        }
      }
    }
    setExpandedEvents(nextEvents);
    setExpandedLines(nextLines);
  }

  function collapseAll() {
    setExpandedEvents(new Set());
    setExpandedLines(new Set());
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">世界杯</h1>
          <p className="text-sm text-[#8b949e]">
            展示北京时间未来 72 小时内尚未开赛的世界杯比赛及 Top Holder
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={expandAll}
            className="rounded-lg border border-[#30363d] px-3 py-2 text-sm text-[#c9d1d9] transition-colors hover:border-[#58a6ff] hover:text-[#58a6ff]"
          >
            全部展开
          </button>
          <button
            onClick={collapseAll}
            className="rounded-lg border border-[#30363d] px-3 py-2 text-sm text-[#c9d1d9] transition-colors hover:border-[#f0883e] hover:text-[#f0883e]"
          >
            全部收起
          </button>
        </div>
      </div>

      {matches.map((match) => {
        const isExpanded = expandedEvents.has(match.event_slug);
        return (
          <section
            key={match.event_slug}
            className="overflow-hidden rounded-2xl border border-[#30363d] bg-[#161b22]"
          >
            <button
              onClick={() => toggleEvent(match.event_slug)}
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left"
            >
              <div className="min-w-0">
                <div className="mb-1 text-lg font-semibold text-[#e6edf3]">
                  {match.event_title}
                </div>
                <div className="flex flex-wrap gap-3 text-sm text-[#8b949e]">
                  <span>{formatBjTime(match.start_time)}</span>
                  <span>{countLines(match)} 个盘口</span>
                </div>
              </div>
              <span className="shrink-0 text-sm text-[#58a6ff]">
                {isExpanded ? "收起" : "展开"}
              </span>
            </button>

            {isExpanded && (
              <div className="border-t border-[#21262d] px-4 py-4">
                <div className="mb-4">
                  <a
                    href={match.event_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-[#58a6ff] hover:underline"
                  >
                    查看 Polymarket 原市场
                  </a>
                </div>

                <div className="flex flex-col gap-4">
                  {GROUPS.map((group) => (
                    <div
                      key={`${match.event_slug}-${group.key}`}
                      className="rounded-xl border border-[#21262d] bg-[#0d1117]"
                    >
                      <div className="border-b border-[#21262d] px-4 py-3 text-sm font-semibold text-[#e6edf3]">
                        {group.label}
                      </div>
                      <div className="p-3">
                        {match.boards_json[group.key].length === 0 ? (
                          <div className="rounded-lg border border-dashed border-[#30363d] px-4 py-5 text-sm text-[#8b949e]">
                            暂无盘口 / 暂无数据
                          </div>
                        ) : (
                          <div className="flex flex-col gap-3">
                            {match.boards_json[group.key].map((line) => {
                              const key = lineKey(match.event_slug, group.key, line);
                              const isLineExpanded = expandedLines.has(key);
                              return (
                                <div
                                  key={key}
                                  className="overflow-hidden rounded-xl border border-[#30363d] bg-[#161b22]"
                                >
                                  <button
                                    onClick={() => toggleLine(key)}
                                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                                  >
                                    <div className="min-w-0">
                                      <div className="truncate text-sm font-medium text-[#e6edf3]">
                                        {line.label}
                                      </div>
                                      <div className="mt-1 flex flex-wrap gap-3 text-xs text-[#8b949e]">
                                        <span>Volume {formatCompactDollar(line.volume)}</span>
                                        <span>Liquidity {formatCompactDollar(line.liquidity)}</span>
                                        <span>{line.sides.length} 边</span>
                                      </div>
                                    </div>
                                    <span className="shrink-0 text-xs text-[#58a6ff]">
                                      {isLineExpanded ? "收起明细" : "展开明细"}
                                    </span>
                                  </button>

                                  {isLineExpanded && (
                                    <div className="border-t border-[#21262d] px-4 py-4">
                                      {line.error && (
                                        <div className="mb-3 rounded-lg border border-[#f8514922] bg-[#f8514911] px-3 py-2 text-sm text-[#f85149]">
                                          Holder 抓取失败：{line.error}
                                        </div>
                                      )}
                                      <div className="mb-3 text-sm text-[#8b949e]">
                                        {line.question || line.label}
                                      </div>
                                      <div className="grid gap-4 md:grid-cols-2">
                                        {line.sides.map((side) => (
                                          <div
                                            key={`${key}-${side.name}`}
                                            className="rounded-xl border border-[#21262d] bg-[#0d1117] p-3"
                                          >
                                            <div className="mb-3 flex items-center justify-between gap-3">
                                              <div className="text-sm font-semibold text-[#e6edf3]">
                                                {side.name}
                                              </div>
                                              <div className="text-xs text-[#8b949e]">
                                                {formatPct(side.price)}
                                              </div>
                                            </div>
                                            {side.holders.length === 0 ? (
                                              <div className="rounded-lg border border-dashed border-[#30363d] px-3 py-4 text-sm text-[#8b949e]">
                                                暂无 holder 数据
                                              </div>
                                            ) : (
                                              <div className="flex flex-col gap-3">
                                                {side.holders.map((holder, idx) => (
                                                  <HolderRow
                                                    key={`${key}-${side.name}-${holder.address}`}
                                                    holder={holder}
                                                    rank={idx + 1}
                                                  />
                                                ))}
                                              </div>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function HolderRow({ holder, rank }: { holder: WorldCupHolder; rank: number }) {
  return (
    <div className="rounded-xl border border-[#21262d] bg-[#161b22] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#58a6ff] text-xs font-bold text-[#0f1117]">
          {rank}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-[#e6edf3]">
            {holder.name}
          </div>
          <div className="truncate text-xs text-[#8b949e]">{holder.address}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs md:grid-cols-3">
        <Metric label="持仓" value={formatCompactDollar(holder.amount)} />
        <Metric label="地址年龄" value={formatAge(holder.address_age_days)} />
        <Metric label="胜率" value={formatRate(holder.win_rate)} />
        <Metric label="总盈利" value={formatSignedDollar(holder.total_pnl)} />
        <Metric label="7天盈利" value={formatSignedDollar(holder.pnl_7d)} />
        <Metric label="30天盈利" value={formatSignedDollar(holder.pnl_30d)} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[#8b949e]">{label}</div>
      <div className="font-medium text-[#e6edf3]">{value}</div>
    </div>
  );
}

function countLines(match: WorldCupMatchBoard): number {
  return (
    match.boards_json.moneyline.length +
    match.boards_json.spread.length +
    match.boards_json.total.length
  );
}

function formatBjTime(value: string): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatPct(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function formatAge(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  if (value >= 365) return `${(value / 365).toFixed(1)} 年`;
  return `${value.toFixed(0)} 天`;
}

function formatRate(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function formatCompactDollar(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}

function formatSignedDollar(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  const prefix = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${prefix}${formatCompactDollar(Math.abs(value))}`;
}
