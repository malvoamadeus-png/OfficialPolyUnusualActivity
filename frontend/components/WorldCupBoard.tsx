"use client";

import { useMemo, useState } from "react";
import {
  WorldCupBoardLine,
  WorldCupBoardSide,
  WorldCupHolder,
  WorldCupMatchBoard,
} from "@/lib/types";

const GROUPS = [
  { key: "moneyline", label: "Moneyline", accent: "from-[#f3f4f6] to-[#d9dde3]" },
  { key: "spread", label: "让分", accent: "from-[#d9ebff] to-[#8cbcf0]" },
  { key: "total", label: "总分", accent: "from-[#f8f1df] to-[#e4c883]" },
] as const;

const HOLDER_FILTER_OPTIONS = [
  { label: "全部", value: 0 },
  { label: "1万美元", value: 10_000 },
  { label: "3万美元", value: 30_000 },
  { label: "5万美元", value: 50_000 },
  { label: "10万美元", value: 100_000 },
  { label: "20万美元", value: 200_000 },
  { label: "50万美元", value: 500_000 },
] as const;

function lineKey(eventSlug: string, boardType: string, line: WorldCupBoardLine): string {
  return `${eventSlug}:${boardType}:${line.condition_id || line.market_slug || line.label}`;
}

export function WorldCupBoard({ matches }: { matches: WorldCupMatchBoard[] }) {
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());
  const [expandedDetails, setExpandedDetails] = useState<Set<string>>(new Set());
  const [selectedLines, setSelectedLines] = useState<Record<string, string>>({});
  const [holderThreshold, setHolderThreshold] = useState<number>(0);

  const filteredMatches = useMemo(
    () => matches.map((match) => filterMatchByHolderAmount(match, holderThreshold)).filter(isNonNull),
    [matches, holderThreshold]
  );

  const allLineKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const match of filteredMatches) {
      for (const group of GROUPS) {
        for (const line of match.boards_json[group.key]) {
          keys.add(lineKey(match.event_slug, group.key, line));
        }
      }
    }
    return keys;
  }, [filteredMatches]);

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

  function toggleDetail(key: string) {
    setExpandedDetails((prev) => {
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
    setExpandedEvents(new Set(filteredMatches.map((match) => match.event_slug)));
    setExpandedDetails(new Set(allLineKeys));
  }

  function collapseAll() {
    setExpandedEvents(new Set());
    setExpandedDetails(new Set());
  }

  function updateSelectedLine(matchSlug: string, boardType: string, key: string) {
    setSelectedLines((prev) => ({ ...prev, [`${matchSlug}:${boardType}`]: key }));
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-[28px] border border-[#253040] bg-[radial-gradient(circle_at_top_left,_rgba(77,132,208,0.18),_transparent_42%),linear-gradient(145deg,#0f1622,#111a28_55%,#10151f)] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.32)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7b90ae]">
              World Cup Match Boards
            </div>
            <h1 className="text-3xl font-semibold text-[#edf2fa]">世界杯</h1>
            <p className="mt-2 max-w-[760px] text-sm leading-6 text-[#97a6bb]">
              展示北京时间未来 72 小时内尚未开赛的世界杯比赛，以及 Moneyline、让分、总分盘口的 Top Holder。
            </p>
          </div>
          <div className="flex flex-col items-stretch gap-3 md:items-end">
            <div className="flex flex-wrap justify-end gap-2">
              {HOLDER_FILTER_OPTIONS.map((option) => {
                const active = holderThreshold === option.value;
                return (
                  <button
                    key={option.value}
                    onClick={() => setHolderThreshold(option.value)}
                    className={`rounded-full px-3 py-2 text-sm font-medium transition ${
                      active
                        ? "border border-[#6eb0ff] bg-[#173152] text-white shadow-[0_8px_20px_rgba(24,52,92,0.28)]"
                        : "border border-[#31435d] bg-[#121c2b] text-[#a9bad3] hover:border-[#4c6586] hover:text-white"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <div className="flex shrink-0 gap-2">
            <button
              onClick={expandAll}
              className="rounded-full border border-[#35517c] bg-[#16243a] px-4 py-2 text-sm text-[#dbe7fb] transition hover:border-[#68a4ff] hover:text-white"
            >
              全部展开
            </button>
            <button
              onClick={collapseAll}
              className="rounded-full border border-[#40384a] bg-[#1b1722] px-4 py-2 text-sm text-[#dfd4ea] transition hover:border-[#f0b36a] hover:text-white"
            >
              全部收起
            </button>
            </div>
          </div>
        </div>
      </div>

      {filteredMatches.length === 0 ? (
        <div className="rounded-[24px] border border-dashed border-[#31435d] bg-[linear-gradient(180deg,#0e1521,#101925)] px-6 py-12 text-center text-[#94a7c3]">
          当前筛选下没有符合条件的持仓
        </div>
      ) : (
      filteredMatches.map((match) => {
        const isExpanded = expandedEvents.has(match.event_slug);
        return (
          <section
            key={match.event_slug}
            className="overflow-hidden rounded-[26px] border border-[#233044] bg-[linear-gradient(180deg,#111a27,#0d141f)] shadow-[0_12px_40px_rgba(0,0,0,0.2)]"
          >
            <button
              onClick={() => toggleEvent(match.event_slug)}
              className="flex w-full items-center justify-between gap-4 px-5 py-5 text-left"
            >
              <div className="min-w-0">
                <div className="mb-2 text-xl font-semibold text-[#eef3fb]">{match.event_title}</div>
                <div className="flex flex-wrap gap-3 text-sm text-[#8ea0ba]">
                  <span>{formatBjTime(match.start_time)}</span>
                  <span>{countLines(match)} 个盘口 line</span>
                </div>
              </div>
              <div className="shrink-0 rounded-full border border-[#31435d] px-3 py-1 text-sm text-[#86b8ff]">
                {isExpanded ? "收起" : "展开"}
              </div>
            </button>

            {isExpanded && (
              <div className="border-t border-[#1e2a3c] px-4 pb-5 pt-4">
                <div className="mb-4">
                  <a
                    href={match.event_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-[#6db1ff] hover:underline"
                  >
                    查看 Polymarket 原市场
                  </a>
                </div>

                <div className="flex flex-col gap-4">
                  {GROUPS.map((group) => (
                    <GroupPanel
                      key={`${match.event_slug}-${group.key}`}
                      match={match}
                      boardType={group.key}
                      label={group.label}
                      accent={group.accent}
                      expandedDetails={expandedDetails}
                      onToggleDetail={toggleDetail}
                      selectedLineKey={selectedLines[`${match.event_slug}:${group.key}`]}
                      onSelectLine={updateSelectedLine}
                    />
                  ))}
                </div>
              </div>
            )}
          </section>
        );
      }))}
    </div>
  );
}

function GroupPanel({
  match,
  boardType,
  label,
  accent,
  expandedDetails,
  onToggleDetail,
  selectedLineKey,
  onSelectLine,
}: {
  match: WorldCupMatchBoard;
  boardType: "moneyline" | "spread" | "total";
  label: string;
  accent: string;
  expandedDetails: Set<string>;
  onToggleDetail: (key: string) => void;
  selectedLineKey?: string;
  onSelectLine: (matchSlug: string, boardType: string, key: string) => void;
}) {
  const lines = match.boards_json[boardType];
  if (lines.length === 0) {
    return null;
  }
  const totalVolume = lines.reduce((sum, line) => sum + (line.volume || 0), 0);
  const selected =
    lines.find((line) => lineKey(match.event_slug, boardType, line) === selectedLineKey) ||
    lines[0] ||
    null;

  return (
    <div className="overflow-hidden rounded-[22px] border border-[#202d3f] bg-[linear-gradient(180deg,#fcfdff,#eef2f8)] text-[#0e1726]">
      <div className="flex flex-col gap-4 px-5 py-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-1 text-[30px] font-semibold tracking-[-0.03em] text-[#0f1726]">{label}</div>
          <div className="flex flex-wrap gap-3 text-sm text-[#68768a]">
            <span>{formatCompactDollar(totalVolume)} 交易量</span>
            <span>{lines.length} 条 line</span>
          </div>
        </div>

        {boardType === "moneyline" ? (
          <div className="grid w-full gap-3 md:max-w-[560px] md:grid-cols-3">
            {lines[0].sides.map((side) => (
              <div
                key={`${match.event_slug}-${boardType}-${side.name}`}
                className={`rounded-2xl bg-gradient-to-b ${accent} px-4 py-4 text-center shadow-[0_8px_0_rgba(32,42,58,0.18)]`}
              >
                <div className="text-sm font-semibold tracking-[0.02em] text-[#445065]">{side.name}</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#0b1220]">
                  {formatCents(side.price)}
                </div>
              </div>
            ))}
          </div>
        ) : selected ? (
          <div className="grid w-full gap-3 md:max-w-[560px] md:grid-cols-2">
            {selected.sides.map((side, idx) => (
              <div
                key={`${match.event_slug}-${boardType}-${selected.market_slug}-${side.name}`}
                className={`rounded-2xl px-4 py-4 text-left shadow-[0_8px_0_rgba(32,42,58,0.18)] ${
                  idx === 0
                    ? "bg-[linear-gradient(180deg,#89bdf4,#5b98d8)] text-white"
                    : "bg-[linear-gradient(180deg,#e79fb1,#d6728a)] text-white"
                }`}
              >
                <div className="text-xs font-semibold uppercase tracking-[0.14em] opacity-80">
                  {sideOutcomeLabel(side, idx)}
                </div>
                <div className="mt-1 text-sm font-semibold opacity-95">{side.name}</div>
                <div className="mt-2 text-3xl font-semibold tracking-[-0.03em]">
                  {formatCents(side.price)}
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {lines.length > 0 && boardType !== "moneyline" && (
        <div className="border-t border-[#d6dce6] bg-white/70 px-4 py-4">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {lines.map((line) => {
              const key = lineKey(match.event_slug, boardType, line);
              const active = selected && key === lineKey(match.event_slug, boardType, selected);
              return (
                <button
                  key={key}
                  onClick={() => onSelectLine(match.event_slug, boardType, key)}
                  className={`relative min-w-[68px] rounded-full px-4 py-2 text-sm font-semibold transition ${
                    active
                      ? "bg-[#0e1726] text-white shadow-[0_8px_20px_rgba(14,23,38,0.18)]"
                      : "bg-[#edf2f7] text-[#64748b] hover:bg-[#dfe6ef]"
                  }`}
                >
                  {line.short_label || line.label}
                  {active && <span className="absolute left-1/2 top-full mt-1 h-2 w-2 -translate-x-1/2 rotate-45 bg-[#0e1726]" />}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {lines.length > 0 && (
        <div className="border-t border-[#d6dce6] bg-[linear-gradient(180deg,#f5f7fb,#eef2f7)] px-4 py-4">
          {boardType === "moneyline" ? (
            <LineDetails
              line={lines[0]}
              lineId={lineKey(match.event_slug, boardType, lines[0])}
              expanded={expandedDetails.has(lineKey(match.event_slug, boardType, lines[0]))}
              onToggleDetail={onToggleDetail}
            />
          ) : selected ? (
            <LineDetails
              line={selected}
              lineId={lineKey(match.event_slug, boardType, selected)}
              expanded={expandedDetails.has(lineKey(match.event_slug, boardType, selected))}
              onToggleDetail={onToggleDetail}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

function LineDetails({
  line,
  lineId,
  expanded,
  onToggleDetail,
}: {
  line: WorldCupBoardLine;
  lineId: string;
  expanded: boolean;
  onToggleDetail: (key: string) => void;
}) {
  return (
    <div className="rounded-[20px] border border-[#d3dae5] bg-white/90">
      <button
        onClick={() => onToggleDetail(lineId)}
        className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left"
      >
        <div className="min-w-0">
          <div className="truncate text-base font-semibold text-[#0f1726]">{line.label}</div>
          <div className="mt-1 flex flex-wrap gap-3 text-xs text-[#64748b]">
            <span>Volume {formatCompactDollar(line.volume)}</span>
            <span>Liquidity {formatCompactDollar(line.liquidity)}</span>
            <span>{line.sides.length} 边</span>
          </div>
        </div>
        <span className="shrink-0 rounded-full border border-[#d3dae5] px-3 py-1 text-xs font-medium text-[#4a5a70]">
          {expanded ? "收起 Holder" : "展开 Holder"}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-[#e0e5ec] px-4 py-4">
          {line.error && (
            <div className="mb-3 rounded-xl border border-[#f5c4c4] bg-[#fff1f1] px-3 py-2 text-sm text-[#bf4444]">
              Holder 抓取失败：{line.error}
            </div>
          )}
          <div className="mb-4 text-sm text-[#64748b]">{line.question || line.label}</div>
          <div className={`grid gap-4 ${line.sides.length >= 3 ? "xl:grid-cols-3" : "md:grid-cols-2"}`}>
            {line.sides.map((side, idx) => (
              <div
                key={`${lineId}-${side.name}`}
                className="rounded-[18px] border border-[#dde3ec] bg-[linear-gradient(180deg,#ffffff,#f7f9fc)] p-3"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#6f7f94]">
                      {sideOutcomeLabel(side, idx)}
                    </div>
                    <div className="truncate text-sm font-semibold text-[#0f1726]">{side.name}</div>
                  </div>
                  <div className="rounded-full bg-[#eef3f8] px-3 py-1 text-xs text-[#5f7087]">
                    {formatPct(side.price)}
                  </div>
                </div>
                {side.holders.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[#d4dbe5] px-3 py-6 text-sm text-[#7b8797]">
                    暂无 holder 数据
                  </div>
                ) : (
                  <div className="flex flex-col gap-3">
                    {side.holders.map((holder, idx) => (
                      <HolderRow
                        key={`${lineId}-${side.name}-${holder.address}`}
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
}

function HolderRow({ holder, rank }: { holder: WorldCupHolder; rank: number }) {
  return (
    <div className="rounded-2xl border border-[#e1e6ee] bg-[#fbfcfe] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0f1726] text-xs font-bold text-white">
          {rank}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-[#0f1726]">{holder.name}</div>
          <div className="truncate text-xs text-[#7b8797]">{holder.address}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs md:grid-cols-3">
        <Metric label="持仓金额" value={formatCompactDollar(holder.amount)} />
        <Metric
          label="地址年龄"
          value={formatAge(holder.address_age_days)}
          highlight={isAddressAgeHot(holder.address_age_days)}
        />
        <Metric label="胜率" value={formatRate(holder.win_rate)} />
        <Metric
          label="总盈利"
          value={formatSignedDollar(holder.total_pnl)}
          highlight={isPnlHot(holder.total_pnl, 1_000_000)}
        />
        <Metric
          label="7天盈利"
          value={formatSignedDollar(holder.pnl_7d)}
          highlight={isPnlHot(holder.pnl_7d, 200_000)}
        />
        <Metric
          label="30天盈利"
          value={formatSignedDollar(holder.pnl_30d)}
          highlight={isPnlHot(holder.pnl_30d, 400_000)}
        />
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  const emphasis = highlight ? "text-[#d1242f] font-bold" : "text-[#172233] font-medium";
  return (
    <div>
      <div className={`mb-1 ${highlight ? "text-[#d1242f] font-bold" : "text-[#7b8797]"}`}>
        {label}
      </div>
      <div className={emphasis}>{value}</div>
    </div>
  );
}

function isAddressAgeHot(value: number | null): boolean {
  return value !== null && Number.isFinite(value) && value < 30;
}

function isPnlHot(value: number | null, threshold: number): boolean {
  return value !== null && Number.isFinite(value) && value > threshold;
}

function sideOutcomeLabel(side: WorldCupBoardSide, fallbackIndex = 0): string {
  const direction = side.direction?.trim();
  if (direction) return direction;
  return fallbackIndex === 0 ? "Yes" : "No";
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

function formatCents(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  return `${Math.round(value * 100)}c`;
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

function filterMatchByHolderAmount(
  match: WorldCupMatchBoard,
  threshold: number
): WorldCupMatchBoard | null {
  if (threshold <= 0) {
    return match;
  }

  const boards_json = {
    moneyline: filterLinesByHolderAmount(match.boards_json.moneyline, threshold),
    spread: filterLinesByHolderAmount(match.boards_json.spread, threshold),
    total: filterLinesByHolderAmount(match.boards_json.total, threshold),
  };

  const visibleCount =
    boards_json.moneyline.length + boards_json.spread.length + boards_json.total.length;

  if (visibleCount <= 0) {
    return null;
  }

  return {
    ...match,
    boards_json,
  };
}

function filterLinesByHolderAmount(
  lines: WorldCupBoardLine[],
  threshold: number
): WorldCupBoardLine[] {
  return lines
    .map((line) => {
      const sides = line.sides
        .map((side) => ({
          ...side,
          holders: side.holders.filter(
            (holder) => holder.amount !== null && Number.isFinite(holder.amount) && holder.amount >= threshold
          ),
        }));

      const hasVisibleHolders = sides.some((side) => side.holders.length > 0);
      if (!hasVisibleHolders) {
        return null;
      }

      return {
        ...line,
        sides,
      };
    })
    .filter(isNonNull);
}

function isNonNull<T>(value: T | null): value is T {
  return value !== null;
}
