"use client";

import { useState } from "react";
import { WhaleAlert } from "@/lib/types";
import { WhaleAlertCard } from "./WhaleAlertCard";

export function WhaleAlertList({ alerts }: { alerts: WhaleAlert[] }) {
  // Group by slug → then by market_question
  const eventMap = new Map<
    string,
    { eventTitle: string; url: string; markets: Map<string, WhaleAlert[]> }
  >();

  for (const a of alerts) {
    if (!eventMap.has(a.slug)) {
      eventMap.set(a.slug, {
        eventTitle: a.event_title,
        url: a.url,
        markets: new Map(),
      });
    }
    const event = eventMap.get(a.slug)!;
    const mList = event.markets.get(a.market_question) || [];
    mList.push(a);
    event.markets.set(a.market_question, mList);
  }

  const slugs = [...eventMap.keys()];
  const [openSlugs, setOpenSlugs] = useState<Set<string>>(new Set());

  const allOpen = slugs.length > 0 && openSlugs.size === slugs.length;

  const toggleAll = () => {
    setOpenSlugs(allOpen ? new Set() : new Set(slugs));
  };

  const toggle = (slug: string) => {
    setOpenSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  if (eventMap.size === 0) {
    return <p className="py-10 text-center text-[#8b949e]">暂无数据</p>;
  }

  return (
    <>
      <div className="mb-5 flex items-end justify-between">
        <p className="text-sm text-[#8b949e]">
          新账户 + 大额持仓 = 可疑信号（注册&lt;30天 · 交易&lt;20次 · 持仓&gt;$10k）
        </p>
        <button
          onClick={toggleAll}
          className="shrink-0 rounded-md border border-[#30363d] px-3 py-1 text-xs text-[#8b949e] transition-colors hover:border-[#58a6ff] hover:text-[#58a6ff]"
        >
          {allOpen ? "收起全部" : "展开全部"}
        </button>
      </div>

      <div className="flex flex-col gap-3.5">
        {[...eventMap.entries()].map(([slug, { eventTitle, url, markets }]) => (
          <WhaleAlertCard
            key={slug}
            eventTitle={eventTitle}
            url={url}
            markets={markets}
            isOpen={openSlugs.has(slug)}
            onToggle={() => toggle(slug)}
          />
        ))}
      </div>
    </>
  );
}
