import { WorldCupBoard } from "@/components/WorldCupBoard";
import { getSupabase } from "@/lib/supabase";
import { WorldCupMatchBoard } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function WorldCupPage() {
  const { data } = await getSupabase()
    .from("world_cup_match_boards")
    .select("*")
    .order("start_time", { ascending: true })
    .limit(60);

  const rows = (data || []) as WorldCupMatchBoard[];
  const tableReady = data !== null;

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-6">
      {!tableReady && (
        <div className="mb-5 rounded-xl border border-[#f0883e33] bg-[#f0883e12] px-4 py-3 text-sm text-[#f0b36a]">
          世界杯数据表尚未迁移到当前 Supabase 项目，建表后页面会自动显示数据。
        </div>
      )}

      {rows.length === 0 ? (
        <div>
          <h1 className="mb-2 text-2xl font-bold">世界杯</h1>
          <p className="mb-5 text-sm text-[#8b949e]">
            展示北京时间未来 72 小时内尚未开赛的世界杯比赛及 Top Holder
          </p>
          <p className="rounded-xl border border-dashed border-[#30363d] px-4 py-10 text-center text-[#8b949e]">
            暂无世界杯比赛数据
          </p>
        </div>
      ) : (
        <WorldCupBoard matches={rows} />
      )}
    </main>
  );
}
