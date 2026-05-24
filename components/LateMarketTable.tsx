"use client";

import { LateMarket } from "@/lib/types";

type SortKey = "time_desc" | "time_asc" | "volume_desc" | "volume_asc";

function formatUsd(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN");
}

function getNextSort(current: SortKey, field: "time" | "volume"): SortKey {
  if (field === "time") {
    return current === "time_asc" ? "time_desc" : "time_asc";
  }
  return current === "volume_asc" ? "volume_desc" : "volume_asc";
}

function getSortLabel(current: SortKey, field: "time" | "volume"): string {
  if (field === "time") {
    return current === "time_asc" ? "时间 ↑" : "时间 ↓";
  }
  return current === "volume_asc" ? "金额 ↑" : "金额 ↓";
}

export function LateMarketTable({
  rows,
  sort,
  minVolume,
  maxVolume,
  startTime,
  endTime,
}: {
  rows: LateMarket[];
  sort: SortKey;
  minVolume: string;
  maxVolume: string;
  startTime: string;
  endTime: string;
}) {
  return (
    <div className="space-y-4">
      <form className="grid gap-3 rounded-xl border border-[#30363d] bg-[#161b22] p-4 md:grid-cols-2 xl:grid-cols-5">
        <label className="text-sm text-[#8b949e]">
          开始时间
          <input
            type="datetime-local"
            name="start"
            defaultValue={startTime}
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e1e4e8] outline-none focus:border-[#58a6ff]"
          />
        </label>

        <label className="text-sm text-[#8b949e]">
          结束时间
          <input
            type="datetime-local"
            name="end"
            defaultValue={endTime}
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e1e4e8] outline-none focus:border-[#58a6ff]"
          />
        </label>

        <label className="text-sm text-[#8b949e]">
          最低金额
          <input
            type="number"
            min="0"
            step="1000"
            name="minVolume"
            defaultValue={minVolume}
            placeholder="100000"
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e1e4e8] outline-none focus:border-[#58a6ff]"
          />
        </label>

        <label className="text-sm text-[#8b949e]">
          最高金额
          <input
            type="number"
            min="0"
            step="1000"
            name="maxVolume"
            defaultValue={maxVolume}
            placeholder="留空"
            className="mt-1 w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e1e4e8] outline-none focus:border-[#58a6ff]"
          />
        </label>

        <div className="flex items-end gap-2">
          <input type="hidden" name="sort" value={sort} />
          <button
            type="submit"
            className="rounded-md bg-[#58a6ff] px-4 py-2 text-sm font-medium text-[#0f1117] transition-opacity hover:opacity-90"
          >
            筛选
          </button>
          <a
            href="/late-markets"
            className="rounded-md border border-[#30363d] px-4 py-2 text-sm text-[#8b949e] transition-colors hover:border-[#58a6ff] hover:text-[#e1e4e8]"
          >
            重置
          </a>
        </div>
      </form>

      <div className="flex flex-wrap items-center gap-2">
        <a
          href={`?sort=${getNextSort(sort, "time")}&start=${encodeURIComponent(startTime)}&end=${encodeURIComponent(endTime)}&minVolume=${encodeURIComponent(minVolume)}&maxVolume=${encodeURIComponent(maxVolume)}`}
          className="rounded-md border border-[#30363d] px-3 py-1.5 text-sm text-[#8b949e] transition-colors hover:border-[#58a6ff] hover:text-[#e1e4e8]"
        >
          {getSortLabel(sort, "time")}
        </a>
        <a
          href={`?sort=${getNextSort(sort, "volume")}&start=${encodeURIComponent(startTime)}&end=${encodeURIComponent(endTime)}&minVolume=${encodeURIComponent(minVolume)}&maxVolume=${encodeURIComponent(maxVolume)}`}
          className="rounded-md border border-[#30363d] px-3 py-1.5 text-sm text-[#8b949e] transition-colors hover:border-[#58a6ff] hover:text-[#e1e4e8]"
        >
          {getSortLabel(sort, "volume")}
        </a>
        <span className="text-xs text-[#6e7681]">共 {rows.length} 条</span>
      </div>

      <div className="overflow-hidden rounded-xl border border-[#30363d] bg-[#161b22]">
        <div className="grid grid-cols-[minmax(0,1.8fr)_180px_180px] gap-3 border-b border-[#21262d] px-4 py-3 text-xs font-medium uppercase tracking-wide text-[#6e7681]">
          <span>标题</span>
          <span>结束时间</span>
          <span className="text-right">累计交易金额</span>
        </div>

        {rows.length === 0 ? (
          <p className="py-12 text-center text-sm text-[#8b949e]">暂无符合条件的数据</p>
        ) : (
          <div>
            {rows.map((row) => (
              <a
                key={row.slug}
                href={row.url}
                target="_blank"
                rel="noopener noreferrer"
                className="grid grid-cols-[minmax(0,1.8fr)_180px_180px] gap-3 border-b border-[#21262d] px-4 py-3 transition-colors hover:bg-[#0d1117]"
              >
                <span className="truncate text-sm font-medium text-[#e1e4e8]">
                  {row.title}
                </span>
                <span className="text-sm text-[#b1bac4]">{formatDate(row.end_date)}</span>
                <span className="text-right text-sm font-semibold text-[#58a6ff]">
                  {formatUsd(row.volume_usd)}
                </span>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
