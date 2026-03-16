"use client";

import { useState } from "react";
import { MarketAnalysis } from "@/lib/types";
import { MatchupBoard } from "@/components/MatchupBoard";

const API_BASE = process.env.NEXT_PUBLIC_MARKET_API_URL || "http://8.159.141.123:8917";

function extractSlug(input: string): string {
  const trimmed = input.trim();
  if (trimmed.includes("/")) {
    return trimmed.replace(/\/+$/, "").split("/").pop() || trimmed;
  }
  return trimmed;
}

export default function AnalyzePage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MarketAnalysis | null>(null);

  async function handleSearch() {
    const slug = extractSlug(input);
    if (!slug) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/analyze?slug=${encodeURIComponent(slug)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `请求失败 (${res.status})`);
      }
      const data = await res.json();
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
        输入市场 slug 或完整 Polymarket 链接，实时分析 Top Holders
      </p>

      <div className="mb-6 flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="例如: cs2-mglz-navi-2026-03-13 或完整链接"
          className="flex-1 rounded-lg border border-[#30363d] bg-[#0d1117] px-4 py-2.5 text-sm text-[#e1e4e8] placeholder-[#6e7681] outline-none focus:border-[#58a6ff]"
        />
        <button
          onClick={handleSearch}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-[#58a6ff] px-5 py-2.5 text-sm font-medium text-[#0f1117] transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {loading ? "分析中..." : "分析"}
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
          正在实时分析，请稍候...
        </div>
      )}

      {result && <MatchupBoard data={result} />}
    </main>
  );
}
