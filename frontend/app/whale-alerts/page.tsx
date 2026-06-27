import { getSupabase } from "@/lib/supabase";
import { WhaleAlert } from "@/lib/types";
import { WhaleAlertList } from "@/components/WhaleAlertList";

export const dynamic = "force-dynamic";
const MIN_POSITION_VALUE = 5_000;
const MAX_ALERT_ROWS = 400;
const RETENTION_HOURS = 48;

export default async function WhaleAlertsPage() {
  const cutoffIso = new Date(Date.now() - RETENTION_HOURS * 60 * 60 * 1000).toISOString();
  const { data } = await getSupabase()
    .from("whale_alerts")
    .select("*")
    .gte("position_value", MIN_POSITION_VALUE)
    .gte("detected_at", cutoffIso)
    .order("detected_at", { ascending: false })
    .limit(MAX_ALERT_ROWS);

  const alerts = (data || []) as WhaleAlert[];

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">大额监控</h1>
      <WhaleAlertList alerts={alerts} />
    </main>
  );
}
