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
  eventTitle,
  url,
  markets,
}: {
  eventTitle: string;
  url: string;
  markets: Map<string, WhaleAlert[]>;
}) {
  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] p-4.5 transition-colors hover:border-[#f0883e]">
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[0.95rem] font-semibold leading-snug text-[#e1e4e8] hover:text-[#f0883e]"
      >
        {eventTitle}
      </a>

      {[...markets.entries()].map(([mq, holders]) => (
        <MarketSection key={mq} question={mq} holders={holders} />
      ))}
    </div>
  );
}

function MarketSection({
  question,
  holders,
}: {
  question: string;
  holders: WhaleAlert[];
}) {
  // Split by side
  const yesHolders = holders.filter((h) => h.side === "Yes");
  const noHolders = holders.filter((h) => h.side !== "Yes");

  return (
    <div className="mt-3 border-t border-[#21262d] pt-3">
      <p className="mb-2 text-sm font-medium text-[#b1bac4]">{question}</p>

      {yesHolders.length > 0 && (
        <div className="mb-2">
          <div className="mb-1 text-[0.7rem] font-bold text-[#3fb950]">
            YES{" "}
            <span className="font-normal text-[#8b949e]">
              @ {((yesHolders[0].side_price ?? 0) * 100).toFixed(1)}¢
            </span>
          </div>
          <div className="space-y-1.5">
            {yesHolders.map((h) => (
              <HolderRow key={h.holder_address} h={h} />
            ))}
          </div>
        </div>
      )}

      {noHolders.length > 0 && (
        <div>
          <div className="mb-1 text-[0.7rem] font-bold text-[#f85149]">
            NO{" "}
            <span className="font-normal text-[#8b949e]">
              @ {((noHolders[0].side_price ?? 0) * 100).toFixed(1)}¢
            </span>
          </div>
          <div className="space-y-1.5">
            {noHolders.map((h) => (
              <HolderRow key={h.holder_address} h={h} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HolderRow({ h }: { h: WhaleAlert }) {
  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-lg bg-[#0d1117] px-3 py-2 text-xs">
      <span className="font-mono text-[#8b949e]">
        {truncAddr(h.holder_address)}
      </span>
      <span className="font-semibold text-[#f0883e]">
        {formatUsd(h.holder_amount)} shares
      </span>
      {h.position_value != null && (
        <span className="text-[#e1e4e8]">
          ≈ {formatUsd(h.position_value)}
        </span>
      )}
      <span className="text-[#6e7681]">
        {h.holder_trades ?? "?"}次交易
      </span>
      <span className="text-[#6e7681]">
        {h.holder_active_days ?? "?"}天
      </span>
    </div>
  );
}
