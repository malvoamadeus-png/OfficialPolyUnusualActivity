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

  // Group by slug
  const grouped = new Map<string, WhaleAlert[]>();
  for (const a of alerts) {
    const list = grouped.get(a.slug) || [];
    list.push(a);
    grouped.set(a.slug, list);
  }

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">大额监控</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        新账户 + 大额持仓 = 可疑信号（注册&lt;30天 · 交易&lt;20次 · 持仓&gt;$10k）
      </p>

      {grouped.size === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {[...grouped.entries()].map(([slug, holders]) => (
            <WhaleAlertCard
              key={slug}
              question={holders[0].question}
              url={holders[0].url}
              holders={holders}
            />
          ))}
        </div>
      )}
    </main>
  );
}
