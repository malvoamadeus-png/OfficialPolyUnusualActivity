import { getSupabase } from "@/lib/supabase";
import { NewMarket } from "@/lib/types";
import { NewMarketCard } from "@/components/NewMarketCard";

export const dynamic = "force-dynamic";

export default async function NewMarketsPage() {
  const { data } = await getSupabase()
    .from("new_markets")
    .select("*")
    .order("detected_at", { ascending: false });

  const markets = (data || []) as NewMarket[];

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">Polymarket上新</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        AI 精选 · 值得关注的新预测市场
      </p>

      {markets.length === 0 ? (
        <p className="py-10 text-center text-[#8b949e]">暂无数据</p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {markets.map((item) => (
            <NewMarketCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
