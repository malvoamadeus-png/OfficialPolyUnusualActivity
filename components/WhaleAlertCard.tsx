import { WhaleAlert } from "@/lib/types";

function truncAddr(addr: string): string {
  return addr.length > 10 ? `${addr.slice(0, 6)}...${addr.slice(-4)}` : addr;
}

function formatUsd(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

export function WhaleAlertCard({
  question,
  url,
  holders,
}: {
  question: string;
  url: string;
  holders: WhaleAlert[];
}) {
  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4.5 transition-colors hover:border-[#f0883e]">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[0.95rem] font-semibold leading-snug text-[#e1e4e8] hover:text-[#f0883e]"
      >
        {question}
      </a>

      <div className="mt-3 border-t border-[#21262d] pt-3">
        <div className="space-y-2">
          {holders.map((h) => (
            <div
              key={h.holder_address}
              className="flex items-center gap-3 rounded-lg bg-[#0d1117] px-3 py-2 text-xs"
            >
              <span
                className={`shrink-0 rounded px-1.5 py-0.5 text-[0.65rem] font-bold ${
                  h.side === "Yes"
                    ? "bg-[#1a3a2a] text-[#3fb950]"
                    : "bg-[#3d1f2a] text-[#f85149]"
                }`}
              >
                {h.side || "?"}
              </span>
              <span className="font-mono text-[#8b949e]">
                {truncAddr(h.holder_address)}
              </span>
              <span className="font-semibold text-[#f0883e]">
                {formatUsd(h.holder_amount)}
              </span>
              <span className="text-[#6e7681]">
                {h.holder_trades ?? "?"}次交易
              </span>
              <span className="text-[#6e7681]">
                {h.holder_active_days ?? "?"}天
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-2.5 text-xs text-[#6e7681]">
        {new Date(holders[0].detected_at).toLocaleString("zh-CN")}
      </div>
    </div>
  );
}
