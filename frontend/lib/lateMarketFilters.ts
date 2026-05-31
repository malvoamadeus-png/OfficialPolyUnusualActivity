import { LateMarket } from "@/lib/types";

const EXCLUDED_CATEGORY_SLUGS = new Set([
  "baseball",
  "basketball",
  "bitcoin",
  "boxing",
  "champions-league",
  "counter-strike",
  "cricket",
  "crypto",
  "crypto-prices",
  "cs2",
  "dota-2",
  "esports",
  "ethereum",
  "football",
  "golf",
  "league-of-legends",
  "lol",
  "mma",
  "nba",
  "nfl",
  "nhl",
  "olympics",
  "pga",
  "soccer",
  "sports",
  "tennis",
  "uefa",
  "wnba",
]);

const EXCLUDED_TITLE_KEYWORDS = [
  "bitcoin",
  "btc",
  "crypto",
  "cryptocurrency",
  "ethereum",
  "eth ",
  "solana",
  "sol ",
  "dogecoin",
  "doge",
  "nba",
  "wnba",
  "nfl",
  "nhl",
  "mlb",
  "ufc",
  "mma",
  "formula 1",
  "f1 ",
  "champions league",
  "uefa",
  "premier league",
  "la liga",
  "serie a",
  "bundesliga",
  "french open",
  "wimbledon",
  "counter-strike",
  "counter strike",
  "cs2",
  "league of legends",
  "lol:",
  "dota",
  "valorant",
];

function normalizeToken(value: string | null | undefined): string {
  return (value || "").trim().toLowerCase();
}

export function isLateMarketVisible(
  row: Pick<LateMarket, "title" | "category" | "end_date">,
  now = Date.now(),
): boolean {
  const endDateTs = new Date(row.end_date).getTime();
  if (!Number.isFinite(endDateTs) || endDateTs <= now) {
    return false;
  }

  const category = normalizeToken(row.category);
  if (category && EXCLUDED_CATEGORY_SLUGS.has(category)) {
    return false;
  }

  const title = normalizeToken(row.title);
  return !EXCLUDED_TITLE_KEYWORDS.some((keyword) => title.includes(keyword));
}
