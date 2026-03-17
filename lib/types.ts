export interface ProbabilityAnalysis {
  question_zh?: string;
  event_summary: string;
  detailed_analysis: string;
  sources: string[];
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

// Market Analyzer types
export interface TraderProfile {
  address: string;
  name: string;
  amount: number;
  win_rate: number | null;
  total_positions: number | null;
  pnl: number | null;
  tags: string | null;
  trades: number | null;
}

export interface OutcomeSide {
  name: string;
  price: number;
  holders: TraderProfile[];
}

export interface MarketAnalysis {
  question: string;
  slug: string;
  sides: [OutcomeSide, OutcomeSide];
}

// ── New Markets (Polymarket上新) ──

export interface NewMarketAnalysis {
  question_zh?: string;
  reason: string;
  appeal_tags: string[];
}

export interface NewMarket {
  id: number;
  slug: string;
  question: string;
  url: string;
  ai_analysis: NewMarketAnalysis | null;
  created_at: string | null;
  detected_at: string;
  batch_id: string | null;
}

// ── Whale Alerts (大额监控) ──

export interface WhaleAlert {
  id: number;
  slug: string;
  question: string;
  url: string;
  holder_address: string;
  holder_name: string | null;
  holder_amount: number;
  holder_trades: number | null;
  holder_active_days: number | null;
  side: string | null;
  detected_at: string;
}
