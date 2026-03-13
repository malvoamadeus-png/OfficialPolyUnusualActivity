import { getSupabase } from "@/lib/supabase";
import { ProbabilityChange } from "@/lib/types";
import { CategoryTabs } from "@/components/CategoryTabs";
import { ChangeCard } from "@/components/ChangeCard";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const { category } = await searchParams;
  const selected = category || "all";

  let query = getSupabase()
    .from("probability_changes")
    .select("*")
    .order("change_timestamp", { ascending: false });

  if (selected !== "all") {
    query = query.eq("category", selected);
  }

  const { data } = await query;
  const changes = (data || []) as ProbabilityChange[];

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">OdailySeer</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        Polymarket 概率异动监控 · AI 原因分析
      </p>

      <CategoryTabs current={selected} />

      {changes.length === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {changes.map((item) => (
            <ChangeCard key={`${item.market_id}-${item.change_timestamp}`} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
