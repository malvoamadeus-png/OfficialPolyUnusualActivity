"use client";

import Link from "next/link";
import { CATEGORIES } from "@/lib/types";

export function CategoryTabs({ current }: { current: string }) {
  return (
    <div className="mb-5 flex flex-wrap gap-2">
      {CATEGORIES.map(({ key, label }) => (
        <Link
          key={key}
          href={key === "all" ? "/" : `/?category=${key}`}
          className={`rounded-2xl border px-3.5 py-1.5 text-xs transition-colors ${
            current === key
              ? "border-[#58a6ff] bg-[#58a6ff] text-[#0f1117]"
              : "border-[#30363d] text-[#8b949e] hover:border-[#58a6ff] hover:text-[#58a6ff]"
          }`}
        >
          {label}
        </Link>
      ))}
    </div>
  );
}
