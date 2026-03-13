export interface ProbabilityAnalysis {
  event_summary: string;
  detailed_analysis: string;
  sources: string[];
  confidence: "high" | "medium" | "low";
}

export interface ProbabilityChange {
  id: number;
  market_id: string;
  slug: string;
  question: string;
  category: string;
  change_timestamp: number;
  prev_timestamp: number;
  prev_price: number;
  curr_price: number;
  log_odds_diff: number;
  analysis: ProbabilityAnalysis | null;
  detected_at: string;
  analyzed_at: string | null;
}

export const CATEGORIES = [
  { key: "all", label: "全部" },
  { key: "politics", label: "政治" },
  { key: "world", label: "国际" },
  { key: "sports", label: "体育" },
  { key: "crypto", label: "加密" },
  { key: "finance", label: "金融" },
  { key: "tech", label: "科技" },
  { key: "culture", label: "文化" },
] as const;
