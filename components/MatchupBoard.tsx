import { MarketAnalysis, TraderProfile } from "@/lib/types";

export function MatchupBoard({ data }: { data: MarketAnalysis }) {
  const [left, right] = data.sides;
  const leftPct = Math.round(left.price * 100);
  const rightPct = Math.round(right.price * 100);

  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] overflow-hidden">
      {/* Header: Question + Probability Bar */}
      <div className="px-5 pt-5 pb-4">
        <h2 className="mb-3 text-center text-base font-semibold leading-snug">
          {data.question}
        </h2>

        {/* VS row */}
        <div className="mb-2 flex items-center justify-between text-sm font-bold">
          <span className="text-[#58a6ff]">{left.name}</span>
          <span className="text-xs text-[#6e7681]">VS</span>
          <span className="text-[#f0883e]">{right.name}</span>
        </div>

        {/* Probability bar */}
        <div className="flex h-7 overflow-hidden rounded-full text-xs font-bold leading-7">
          <div
            className="flex items-center justify-center bg-[#58a6ff] text-[#0f1117] transition-all"
            style={{ width: `${leftPct}%` }}
          >
            {leftPct}%
          </div>
          <div
            className="flex items-center justify-center bg-[#f0883e] text-[#0f1117] transition-all"
            style={{ width: `${rightPct}%` }}
          >
            {rightPct}%
          </div>
        </div>
      </div>

      {/* Holders grid */}
      <div className="grid grid-cols-2 gap-px bg-[#21262d]">
        <HolderColumn holders={left.holders} side="left" />
        <HolderColumn holders={right.holders} side="right" />
      </div>
    </div>
  );
}
// PLACEHOLDER_CONTINUE

function HolderColumn({
  holders,
  side,
}: {
  holders: TraderProfile[];
  side: "left" | "right";
}) {
  const accent = side === "left" ? "#58a6ff" : "#f0883e";

  return (
    <div className="flex flex-col gap-px bg-[#21262d]">
      {holders.length === 0 ? (
        <div className="bg-[#161b22] p-4 text-center text-xs text-[#6e7681]">
          暂无数据
        </div>
      ) : (
        holders.map((h, i) => (
          <HolderCard key={h.address} holder={h} rank={i + 1} accent={accent} />
        ))
      )}
    </div>
  );
}

function HolderCard({
  holder,
  rank,
  accent,
}: {
  holder: TraderProfile;
  rank: number;
  accent: string;
}) {
  const pnlColor =
    holder.pnl !== null
      ? holder.pnl >= 0
        ? "text-[#3fb950]"
        : "text-[#f85149]"
      : "text-[#6e7681]";

  const winRateColor =
    holder.win_rate !== null
      ? holder.win_rate >= 0.55
        ? "text-[#3fb950]"
        : holder.win_rate >= 0.45
          ? "text-[#d29922]"
          : "text-[#f85149]"
      : "text-[#6e7681]";

  return (
    <div className="bg-[#161b22] px-4 py-3">
      {/* Name row */}
      <div className="mb-1.5 flex items-center gap-2">
        <span
          className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.65rem] font-bold text-[#0f1117]"
          style={{ background: accent }}
        >
          {rank}
        </span>
        <span className="truncate text-sm font-semibold">{holder.name}</span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-1 text-xs">
        <div>
          <div className="text-[#6e7681]">持仓</div>
          <div className="font-medium">${formatNum(holder.amount)}</div>
        </div>
        <div>
          <div className="text-[#6e7681]">胜率</div>
          <div className={`font-medium ${winRateColor}`}>
            {holder.win_rate !== null
              ? `${(holder.win_rate * 100).toFixed(1)}%`
              : "N/A"}
            {holder.total_positions !== null && (
              <span className="text-[#6e7681]"> ({holder.total_positions})</span>
            )}
          </div>
        </div>
        <div>
          <div className="text-[#6e7681]">PnL</div>
          <div className={`font-medium ${pnlColor}`}>
            {holder.pnl !== null
              ? `${holder.pnl >= 0 ? "+" : ""}$${formatNum(Math.abs(holder.pnl))}`
              : "N/A"}
          </div>
        </div>
        <div>
          <div className="text-[#6e7681]">交易</div>
          <div className="font-medium">
            {holder.trades !== null ? formatNum(holder.trades) : "N/A"}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toFixed(0);
}
