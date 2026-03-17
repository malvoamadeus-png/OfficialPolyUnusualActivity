import { getSupabase } from "@/lib/supabase";
import { WhaleAlert } from "@/lib/types";
import { WhaleAlertList } from "@/components/WhaleAlertList";

export const dynamic = "force-dynamic";

export default async function WhaleAlertsPage() {
  const { data } = await getSupabase()
    .from("whale_alerts")
    .select("*")
    .order("detected_at", { ascending: false })
    .limit(200);

  const alerts = (data || []) as WhaleAlert[];

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">大额监控</h1>
      <WhaleAlertList alerts={alerts} />
    </main>
  );
}
