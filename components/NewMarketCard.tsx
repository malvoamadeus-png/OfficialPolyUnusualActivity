import { NewMarket, NewMarketAnalysis } from "@/lib/types";

const TAG_COLORS = [
  "bg-[#1f3a5f] text-[#58a6ff]",
  "bg-[#3b2f1e] text-[#d29922]",
  "bg-[#2a1f3d] text-[#bc8cff]",
  "bg-[#1e3a2f] text-[#3fb950]",
  "bg-[#3d1f2a] text-[#f85149]",
];

export function NewMarketCard({ item }: { item: NewMarket }) {
  const analysis = item.ai_analysis as NewMarketAnalysis | null;
  const displayTitle = analysis?.question_zh || item.question;
  const createdTime = item.created_at
    ? new Date(item.created_at).toLocaleString("zh-CN")
    : null;
  const embedSrc = `https://embed.polymarket.com/market?market=${item.slug}&height=300`;

  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4.5 transition-colors hover:border-[#58a6ff]">
      <div className="flex items-start justify-between gap-3">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 text-[0.95rem] font-semibold leading-snug text-[#e1e4e8] hover:text-[#58a6ff]"
        >
          {displayTitle}
        </a>
      </div>

      {analysis && (
        <div className="mt-3 border-t border-[#21262d] pt-3">
          <p className="text-sm leading-relaxed text-[#b1bac4]">
            {analysis.reason}
          </p>
          {analysis.appeal_tags?.length > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {analysis.appeal_tags.map((tag, i) => (
                <span
                  key={tag}
                  className={`rounded-full px-2.5 py-0.5 text-[0.7rem] font-medium ${TAG_COLORS[i % TAG_COLORS.length]}`}
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Polymarket Embed */}
      <div className="mt-3 overflow-hidden rounded-lg">
        <iframe
          title={item.question}
          src={embedSrc}
          width="100%"
          height="300"
          frameBorder="0"
          allowTransparency
          className="block"
        />
      </div>

      <div className="mt-2.5 flex items-center gap-3 text-xs text-[#6e7681]">
        {createdTime && <span>创建于 {createdTime}</span>}
      </div>
    </div>
  );
}
