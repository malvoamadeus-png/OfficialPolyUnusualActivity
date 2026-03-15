"use client";

import { useState } from "react";
import { MarketAnalysis } from "@/lib/types";
import { MatchupBoard } from "@/components/MatchupBoard";
import { getSupabase } from "@/lib/supabase";

export default function AnalyzePage() {
  const [slug, setSlug] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MarketAnalysis | null>(null);

  async function handleSearch() {
    const searchSlug = slug.trim();
    if (!searchSlug) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const { data, error: dbError } = await getSupabase()
        .from("market_analysis")
        .select("*")
        .eq("slug", searchSlug)
        .single();

      if (dbError) throw new Error("未找到该市场分析数据");
      if (!data) throw new Error("未找到该市场分析数据");

      setResult(data as MarketAnalysis);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-[960px] px-4 py-6">
      <h1 className="text-2xl font-bold">Market Analyzer</h1>
      <p className="mb-5 text-sm text-[#8b949e]">
        输入市场 slug 查看分析（需先用 Python 脚本生成数据）
      </p>

      <div className="mb-6 flex gap-3">
        <input
          type="text"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="例如: cs2-mglz-navi-2026-03-13"
          className="flex-1 rounded-lg border border-[#30363d] bg-[#0d1117] px-4 py-2.5 text-sm text-[#e1e4e8] placeholder-[#6e7681] outline-none focus:border-[#58a6ff]"
        />
        <button
          onClick={handleSearch}
          disabled={loading || !slug.trim()}
          className="rounded-lg bg-[#58a6ff] px-5 py-2.5 text-sm font-medium text-[#0f1117] transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {loading ? "查询中..." : "查询"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-[#f8514922] bg-[#f8514911] px-4 py-3 text-sm text-[#f85149]">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16 text-[#8b949e]">
          <svg className="mr-3 h-5 w-5 animate-spin" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          正在查询...
        </div>
      )}

      {result && <MatchupBoard data={result} />}
    </main>
  );
}
