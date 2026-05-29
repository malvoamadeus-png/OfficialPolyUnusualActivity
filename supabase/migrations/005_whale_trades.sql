-- whale_trades: 大额交易活动
CREATE TABLE whale_trades (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_hash TEXT NOT NULL UNIQUE,
    proxy_wallet TEXT NOT NULL,
    name TEXT,
    side TEXT NOT NULL,
    size NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    outcome TEXT,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    event_slug TEXT,
    icon TEXT,
    timestamp BIGINT NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_whale_trades_timestamp ON whale_trades (timestamp DESC);

-- RLS
ALTER TABLE whale_trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon can read whale_trades" ON whale_trades FOR SELECT TO anon USING (true);
CREATE POLICY "service can all whale_trades" ON whale_trades FOR ALL TO service_role USING (true);
