import { ProbabilityChange, ProbabilityAnalysis, CATEGORIES } from "@/lib/types";

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

  const analysis = item.analysis as ProbabilityAnalysis | null;

  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4.5 transition-colors hover:border-[#58a6ff]">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <h3 className="flex-1 text-[0.95rem] font-semibold leading-snug">
          {item.question || item.slug}
        </h3>
        <span className="shrink-0 rounded-lg bg-[#1f2937] px-2 py-0.5 text-[0.7rem] text-[#8b949e]">
          {getCategoryLabel(item.category)}
        </span>
      </div>

      {/* Price row */}
      <div className="mt-2.5 flex items-center gap-3 text-sm">
        <span className={`text-base font-bold ${color}`}>
          {prevPct}% {arrow} {currPct}%
        </span>
        <span className="text-[#8b949e]">{"\u0394"} {diff}</span>
        <span className="ml-auto text-xs text-[#6e7681]">{time}</span>
      </div>

      {/* Analysis */}
      {analysis ? (
        <AnalysisSection analysis={analysis} />
      ) : (
        <p className="mt-3 text-xs italic text-[#6e7681]">
          等待 AI 分析...
        </p>
      )}
    </div>
  );
}

const confColors: Record<string, string> = {
  high: "#3fb950",
  medium: "#d29922",
  low: "#f85149",
};

function AnalysisSection({ analysis }: { analysis: ProbabilityAnalysis }) {
  const confColor = confColors[analysis.confidence] || "#8b949e";

  return (
    <div className="mt-3.5 border-t border-[#21262d] pt-3.5">
      <p className="mb-2 font-semibold leading-relaxed">
        {analysis.event_summary}
      </p>
      <p className="mb-2 text-sm leading-relaxed text-[#b1bac4]">
        {analysis.detailed_analysis}
      </p>
      {analysis.sources?.length > 0 && (
        <div className="mb-2 break-all text-xs text-[#6e7681]">
          来源：
          {analysis.sources.map((s, i) => (
            <span key={i}>
              {i > 0 && <br />}
              {s.startsWith("http") ? (
                <a
                  href={s}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#58a6ff] hover:underline"
                >
                  {s}
                </a>
              ) : (
                s
              )}
            </span>
          ))}
        </div>
      )}
      <span
        className="rounded-lg px-2 py-0.5 text-[0.7rem]"
        style={{
          background: `${confColor}22`,
          color: confColor,
        }}
      >
        置信度: {analysis.confidence}
      </span>
    </div>
  );
}
