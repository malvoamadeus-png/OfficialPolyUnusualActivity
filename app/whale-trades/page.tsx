import { getSupabase } from "@/lib/supabase";
import { WhaleTrade } from "@/lib/types";
import { WhaleTradeList } from "@/components/WhaleTradeList";

export const dynamic = "force-dynamic";

export default async function WhaleTradesPage() {
  const { data } = await getSupabase()
    .from("whale_trades")
    .select("*")
    .order("timestamp", { ascending: false })
    .limit(200);

  const trades = (data || []) as WhaleTrade[];

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">大额活动</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        Polymarket 实时大额交易（&gt;$10k），每20分钟更新
      </p>
      <WhaleTradeList trades={trades} />
    </main>
  );
}
