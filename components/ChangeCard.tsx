import { ProbabilityChange, CATEGORIES } from "@/lib/types";

function getCategoryLabel(key: string) {
  return CATEGORIES.find((c) => c.key === key)?.label || key;
}

export function ChangeCard({ item }: { item: ProbabilityChange }) {
  const up = item.curr_price > item.prev_price;
  const arrow = up ? "\u2191" : "\u2193";
  const color = up ? "text-[#3fb950]" : "text-[#f85149]";
  const prevPct = (item.prev_price * 100).toFixed(1);
  const currPct = (item.curr_price * 100).toFixed(1);
  const time = new Date(item.change_timestamp * 1000).toLocaleString("zh-CN");
  const diff = item.log_odds_diff.toFixed(3);
  const polymarketUrl = `https://polymarket.com/event/${item.slug}`;

  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4.5 transition-colors hover:border-[#58a6ff]">
      <div className="flex items-start justify-between gap-3">
        <a
          href={polymarketUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 text-[0.95rem] font-semibold leading-snug hover:text-[#58a6ff]"
        >
          {item.question || item.slug}
        </a>
        <span className="shrink-0 rounded-lg bg-[#1f2937] px-2 py-0.5 text-[0.7rem] text-[#8b949e]">
          {getCategoryLabel(item.category)}
        </span>
      </div>

      <div className="mt-2.5 flex items-center gap-3 text-sm">
        <span className={`text-base font-bold ${color}`}>
          {prevPct}% {arrow} {currPct}%
        </span>
        <span className="text-[#8b949e]">{"\u0394"} {diff}</span>
        <span className="ml-auto text-xs text-[#6e7681]">{time}</span>
      </div>
    </div>
  );
}
