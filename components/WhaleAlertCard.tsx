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
  isOpen,
  onToggle,
}: {
  eventTitle: string;
  url: string;
  markets: Map<string, WhaleAlert[]>;
  isOpen: boolean;
  onToggle: () => void;
}) {
  // Count total holders across all markets
  let total = 0;
  markets.forEach((holders) => (total += holders.length));

  return (
    <div className="rounded-xl border border-[#30363d] bg-[#161b22] transition-colors hover:border-[#f0883e]">
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-2 p-4.5 text-left"
      >
        <svg
          className={`h-3.5 w-3.5 shrink-0 text-[#6e7681] transition-transform ${isOpen ? "rotate-90" : ""}`}
          viewBox="0 0 16 16"
          fill="currentColor"
        >
          <path d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06Z" />
        </svg>
        <span className="text-[0.95rem] font-semibold leading-snug text-[#e1e4e8]">
          {eventTitle}
        </span>
        <span className="ml-auto shrink-0 text-xs text-[#6e7681]">
          {total} 条信号
        </span>
      </button>

      {isOpen && (
        <div className="px-4.5 pb-4.5">
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="mb-1 inline-block text-xs text-[#58a6ff] hover:underline"
          >
            Polymarket ↗
          </a>
          {[...markets.entries()].map(([mq, holders]) => (
            <MarketSection key={mq} question={mq} holders={holders} />
          ))}
        </div>
      )}
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
