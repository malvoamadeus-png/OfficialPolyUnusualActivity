import { WorldCupFinishedList } from "@/components/WorldCupFinishedList";
import { getSupabase } from "@/lib/supabase";
import { WorldCupFinishedPosition } from "@/lib/types";

export const dynamic = "force-dynamic";

const PROFIT_OPTIONS = new Set([30_000, 50_000, 100_000]);

function resolveProfit(raw: string | undefined): number {
  const value = Number(raw || 30_000);
  return PROFIT_OPTIONS.has(value) ? value : 30_000;
}

export default async function WorldCupFinishedPage({
  searchParams,
}: {
  searchParams: Promise<{ profit?: string }>;
}) {
  const { profit } = await searchParams;
  const selectedProfit = resolveProfit(profit);

  const { data, error } = await getSupabase()
    .from("world_cup_finished_positions")
    .select("*")
    .gte("profit_amount", selectedProfit)
    .order("event_end_time", { ascending: false })
    .order("profit_amount", { ascending: false })
    .limit(300);

  const rows = (data || []) as WorldCupFinishedPosition[];
  const tableReady = !error;

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-6">
      {!tableReady && (
        <div className="mb-5 rounded-xl border border-[#f0883e33] bg-[#f0883e12] px-4 py-3 text-sm text-[#f0b36a]">
          世界杯完结数据表尚未迁移到当前 Supabase 项目，迁移完成后页面会自动显示数据。
        </div>
      )}
      <WorldCupFinishedList rows={rows} selectedProfit={selectedProfit} />
    </main>
  );
}
