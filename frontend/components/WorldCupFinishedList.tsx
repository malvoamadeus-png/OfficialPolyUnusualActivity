import Link from "next/link";
import { WorldCupFinishedPosition } from "@/lib/types";

const PROFIT_OPTIONS = [
  { value: 30_000, label: "3万美元" },
  { value: 50_000, label: "5万美元" },
  { value: 100_000, label: "10万美元" },
] as const;

const BOARD_LABELS: Record<string, string> = {
  moneyline: "Moneyline",
  spread: "让分",
  total: "总分",
};

export function WorldCupFinishedList({
  rows,
  selectedProfit,
}: {
  rows: WorldCupFinishedPosition[];
  selectedProfit: number;
}) {
  const grouped = groupByEvent(rows);

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-[28px] border border-[#253040] bg-[radial-gradient(circle_at_top_left,_rgba(224,154,47,0.16),_transparent_42%),linear-gradient(145deg,#101a24,#122234_58%,#0d141d)] p-5 shadow-[0_22px_70px_rgba(0,0,0,0.32)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-[#aeb9c8]">
              World Cup Finished
            </div>
            <h1 className="text-3xl font-semibold text-[#edf2fa]">世界杯（完结）</h1>
            <p className="mt-2 max-w-[760px] text-sm leading-6 text-[#9bacbf]">
              展示过去 48 小时已结束的世界杯比赛中，盈利超过指定阈值的地址表现。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {PROFIT_OPTIONS.map((option) => {
              const active = selectedProfit === option.value;
              return (
                <Link
                  key={option.value}
                  href={`/world-cup-finished?profit=${option.value}`}
                  className={`rounded-full px-3 py-2 text-sm font-medium transition ${
                    active
                      ? "border border-[#f1b45a] bg-[#3a2612] text-[#fff1d8] shadow-[0_8px_20px_rgba(121,77,25,0.25)]"
                      : "border border-[#364659] bg-[#111c29] text-[#aebfd0] hover:border-[#f1b45a] hover:text-white"
                  }`}
                >
                  盈利 ≥ {option.label}
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      {grouped.length === 0 ? (
        <div className="rounded-[24px] border border-dashed border-[#31435d] bg-[linear-gradient(180deg,#0e1521,#101925)] px-6 py-12 text-center text-[#94a7c3]">
          当前盈利筛选下暂无完结世界杯数据
        </div>
      ) : (
        grouped.map((group) => (
          <section
            key={group.event_slug}
            className="overflow-hidden rounded-[26px] border border-[#233044] bg-[linear-gradient(180deg,#111a27,#0d141f)] shadow-[0_12px_40px_rgba(0,0,0,0.2)]"
          >
            <div className="border-b border-[#1e2a3c] px-5 py-5">
              <div className="mb-2 text-xl font-semibold text-[#eef3fb]">{group.event_title}</div>
              <div className="flex flex-wrap gap-3 text-sm text-[#8ea0ba]">
                <span>完赛时间 {formatBjTime(group.event_end_time)}</span>
                <span>{group.rows.length} 条盈利记录</span>
                <a
                  href={group.event_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#6db1ff] hover:underline"
                >
                  查看 Polymarket 原市场
                </a>
              </div>
            </div>

            <div className="flex flex-col gap-3 px-4 py-4">
              {group.rows.map((row) => (
                <article
                  key={`${row.market_slug}:${row.address}:${row.market_label}`}
                  className="rounded-[20px] border border-[#2b3950] bg-[linear-gradient(180deg,#182433,#131d2a)] p-4"
                >
                  <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-[#5b6e87] bg-[#101a27] px-2.5 py-1 text-xs font-semibold text-[#d3e2f7]">
                          {BOARD_LABELS[row.board_type] || row.board_type}
                        </span>
                        <span className="rounded-full border border-[#5c4930] bg-[#2b2117] px-2.5 py-1 text-xs font-semibold text-[#f2cd96]">
                          {row.market_label}
                        </span>
                      </div>
                      <div className="text-sm leading-6 text-[#cdd8e7]">{row.market_question}</div>
                    </div>
                    <div className="shrink-0 text-left md:text-right">
                      <div className="text-xs text-[#8293aa]">盈利金额</div>
                      <div className="text-2xl font-semibold tracking-[-0.03em] text-[#ffd58e]">
                        {formatMoney(row.profit_amount)}
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-3 text-sm text-[#d7e0eb] md:grid-cols-4">
                    <MetricBlock label="地址" value={row.address} mono />
                    <MetricBlock label="投注金额" value={formatMoney(row.bet_amount)} />
                    <MetricBlock label="盈利金额" value={formatMoney(row.profit_amount)} hot />
                    <MetricBlock
                      label="结算时间"
                      value={row.position_closed_at ? formatBjTime(row.position_closed_at) : formatBjTime(row.event_end_time)}
                    />
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function MetricBlock({
  label,
  value,
  mono = false,
  hot = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  hot?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-[#243245] bg-[#0f1723] px-3 py-3">
      <div className="mb-1 text-xs text-[#7f90a8]">{label}</div>
      <div
        className={`text-sm ${
          mono ? "break-all font-mono text-[12px]" : "font-medium"
        } ${hot ? "text-[#ffd58e]" : "text-[#edf2fa]"}`}
      >
        {value}
      </div>
    </div>
  );
}

function groupByEvent(rows: WorldCupFinishedPosition[]) {
  const grouped = new Map<
    string,
    {
      event_slug: string;
      event_title: string;
      event_end_time: string;
      event_url: string;
      rows: WorldCupFinishedPosition[];
    }
  >();

  for (const row of rows) {
    const existing = grouped.get(row.event_slug);
    if (existing) {
      existing.rows.push(row);
      continue;
    }
    grouped.set(row.event_slug, {
      event_slug: row.event_slug,
      event_title: row.event_title,
      event_end_time: row.event_end_time,
      event_url: row.event_url,
      rows: [row],
    });
  }

  return [...grouped.values()].map((group) => ({
    ...group,
    rows: [...group.rows].sort((a, b) => b.profit_amount - a.profit_amount),
  }));
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

function formatMoney(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "N/A";
  if (Math.abs(value) >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toFixed(0)}`;
}
