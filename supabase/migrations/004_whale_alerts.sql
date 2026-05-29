-- Whale Alerts: 新大额监控 (v2)
-- 数据挂在 market 级别，区分 yes/no 方向，含份额价值

DROP TABLE IF EXISTS whale_alerts CASCADE;

CREATE TABLE whale_alerts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL,
    event_title TEXT NOT NULL,
    url TEXT NOT NULL,
    market_question TEXT NOT NULL,
    holder_address TEXT NOT NULL,
    holder_name TEXT,
    holder_amount NUMERIC NOT NULL,
    holder_trades INTEGER,
    holder_active_days INTEGER,
    side TEXT,
    side_price NUMERIC,
    position_value NUMERIC,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(slug, market_question, holder_address)
);

-- RLS
ALTER TABLE whale_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_whale_alerts" ON whale_alerts
    FOR SELECT TO anon USING (true);

CREATE POLICY "service_full_whale_alerts" ON whale_alerts
    FOR ALL TO service_role USING (true) WITH CHECK (true);
