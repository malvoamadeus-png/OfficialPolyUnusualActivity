import { getSupabase } from "@/lib/supabase";
import { WhaleAlert } from "@/lib/types";
import { WhaleAlertCard } from "@/components/WhaleAlertCard";

export const dynamic = "force-dynamic";

export default async function WhaleAlertsPage() {
  const { data } = await getSupabase()
    .from("whale_alerts")
    .select("*")
    .order("detected_at", { ascending: false })
    .limit(200);

  const alerts = (data || []) as WhaleAlert[];

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

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">大额监控</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        新账户 + 大额持仓 = 可疑信号（注册&lt;30天 · 交易&lt;20次 · 持仓&gt;$10k）
      </p>

      {eventMap.size === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {[...eventMap.entries()].map(([slug, { eventTitle, url, markets }]) => (
            <WhaleAlertCard
              key={slug}
              eventTitle={eventTitle}
              url={url}
              markets={markets}
            />
          ))}
        </div>
      )}
    </main>
  );
}
