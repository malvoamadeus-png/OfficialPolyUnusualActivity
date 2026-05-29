import { LateMarketTable } from "@/components/LateMarketTable";
import { getSupabase } from "@/lib/supabase";
import { LateMarket } from "@/lib/types";

export const dynamic = "force-dynamic";

type SortKey = "time_desc" | "time_asc" | "volume_desc" | "volume_asc";

function normalizeSort(value: string | undefined): SortKey {
  if (
    value === "time_desc" ||
    value === "time_asc" ||
    value === "volume_desc" ||
    value === "volume_asc"
  ) {
    return value;
  }
  return "time_asc";
}

function toNumber(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toTimestamp(value: string | undefined): number | null {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  return Number.isFinite(parsed) ? parsed : null;
}

export default async function LateMarketsPage({
  searchParams,
}: {
  searchParams: Promise<{
    sort?: string;
    minVolume?: string;
    maxVolume?: string;
    start?: string;
    end?: string;
  }>;
}) {
  const params = await searchParams;
  const sort = normalizeSort(params.sort);
  const minVolume = toNumber(params.minVolume);
  const maxVolume = toNumber(params.maxVolume);
  const startTs = toTimestamp(params.start);
  const endTs = toTimestamp(params.end);

  const { data } = await getSupabase()
    .from("late_markets")
    .select("*")
    .limit(500);

  const tableReady = data !== null;

  let rows = ((data || []) as LateMarket[]).filter((row) => {
    const endDateTs = new Date(row.end_date).getTime();

    if (minVolume !== null && row.volume_usd < minVolume) return false;
    if (maxVolume !== null && row.volume_usd > maxVolume) return false;
    if (startTs !== null && endDateTs < startTs) return false;
    if (endTs !== null && endDateTs > endTs) return false;
    return true;
  });

  rows = rows.sort((a, b) => {
    if (sort === "time_desc") {
      return new Date(b.end_date).getTime() - new Date(a.end_date).getTime();
    }
    if (sort === "time_asc") {
      return new Date(a.end_date).getTime() - new Date(b.end_date).getTime();
    }
    if (sort === "volume_desc") {
      return b.volume_usd - a.volume_usd;
    }
    return a.volume_usd - b.volume_usd;
  });

  return (
    <main className="mx-auto max-w-[1120px] px-4 py-6">
      <h1 className="text-2xl font-bold">尾盘发现</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        近 30 天内将结束、累计交易金额超过 10 万美元的 Polymarket 题目
      </p>

      {!tableReady && (
        <div className="mb-5 rounded-xl border border-[#f0883e33] bg-[#f0883e12] px-4 py-3 text-sm text-[#f0b36a]">
          尾盘发现数据表尚未迁移到当前 Supabase 项目，页面会在建表后自动显示数据。
        </div>
      )}

      <LateMarketTable
        rows={rows}
        sort={sort}
        minVolume={params.minVolume || ""}
        maxVolume={params.maxVolume || ""}
        startTime={params.start || ""}
        endTime={params.end || ""}
      />
    </main>
  );
}
