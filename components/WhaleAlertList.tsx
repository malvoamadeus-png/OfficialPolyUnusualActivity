"use client";

import { useMemo, useState } from "react";
import { WhaleAlert } from "@/lib/types";
import { WhaleAlertCard } from "./WhaleAlertCard";

type Tab = "normal" | "endgame";

const ENDGAME_PRICE_THRESHOLD = 0.95;

type EventGroup = {
  eventTitle: string;
  url: string;
  markets: Map<string, WhaleAlert[]>;
};

function groupAlertsByEvent(alerts: WhaleAlert[]): Map<string, EventGroup> {
  const eventMap = new Map<string, EventGroup>();

  for (const alert of alerts) {
    if (!eventMap.has(alert.slug)) {
      eventMap.set(alert.slug, {
        eventTitle: alert.event_title,
        url: alert.url,
        markets: new Map(),
      });
    }

    const event = eventMap.get(alert.slug)!;
    const holders = event.markets.get(alert.market_question) || [];
    holders.push(alert);
    event.markets.set(alert.market_question, holders);
  }

  return eventMap;
}

function getOpenKey(tab: Tab, slug: string): string {
  return `${tab}:${slug}`;
}

export function WhaleAlertList({ alerts }: { alerts: WhaleAlert[] }) {
  const [tab, setTab] = useState<Tab>("normal");
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());

  const normalAlerts = useMemo(
    () => alerts.filter((a) => (a.side_price ?? 0) <= ENDGAME_PRICE_THRESHOLD),
    [alerts],
  );
  const endgameAlerts = useMemo(
    () => alerts.filter((a) => (a.side_price ?? 0) > ENDGAME_PRICE_THRESHOLD),
    [alerts],
  );

  const currentAlerts = tab === "normal" ? normalAlerts : endgameAlerts;
  const eventMap = useMemo(() => groupAlertsByEvent(currentAlerts), [currentAlerts]);
  const slugs = useMemo(() => [...eventMap.keys()], [eventMap]);

  const allOpen =
    slugs.length > 0 && slugs.every((slug) => openKeys.has(getOpenKey(tab, slug)));

  const toggleAll = () => {
    setOpenKeys((prev) => {
      const next = new Set(prev);

      if (allOpen) {
        for (const slug of slugs) {
          next.delete(getOpenKey(tab, slug));
        }
      } else {
        for (const slug of slugs) {
          next.add(getOpenKey(tab, slug));
        }
      }

      return next;
    });
  };

  const toggle = (slug: string) => {
    const key = getOpenKey(tab, slug);
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <>
      <div className="mb-3 flex items-center gap-4">
        {(["normal", "endgame"] as Tab[]).map((k) => {
          const label = k === "normal" ? "正常" : "尾盘";
          const count = k === "normal" ? normalAlerts.length : endgameAlerts.length;
          const active = tab === k;
          return (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                active
                  ? "bg-[#30363d] text-[#e1e4e8]"
                  : "text-[#8b949e] hover:text-[#e1e4e8]"
              }`}
            >
              {label}
              <span className="ml-1 text-xs text-[#6e7681]">{count}</span>
            </button>
          );
        })}
      </div>

      {currentAlerts.length === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <>
          <div className="mb-5 flex items-end justify-between">
            <p className="text-sm text-[#8b949e]">
              新账户 + 大额持仓 = 可疑信号（注册&lt;30天 · 交易&lt;20次 · 持仓&gt;$10k · 仓位价值≈$5k）
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
                key={`${tab}-${slug}`}
                eventTitle={eventTitle}
                url={url}
                markets={markets}
                isOpen={openKeys.has(getOpenKey(tab, slug))}
                onToggle={() => toggle(slug)}
              />
            ))}
          </div>
        </>
      )}
    </>
  );
}
