-- Supabase SQL: 创建 probability_changes 表
-- 在 Supabase Dashboard → SQL Editor 中执行

CREATE TABLE IF NOT EXISTS probability_changes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    market_id TEXT NOT NULL,
    slug TEXT,
    question TEXT,
    category TEXT,
    change_timestamp BIGINT NOT NULL,
    prev_timestamp BIGINT NOT NULL,
    prev_price DOUBLE PRECISION,
    curr_price DOUBLE PRECISION,
    log_odds_diff DOUBLE PRECISION,
    analysis JSONB,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    analyzed_at TIMESTAMPTZ,
    UNIQUE (market_id, change_timestamp)
);

-- RLS: 开启行级安全
ALTER TABLE probability_changes ENABLE ROW LEVEL SECURITY;

-- 允许匿名用户只读（前端用 anon key）
CREATE POLICY "Allow anonymous read"
    ON probability_changes
    FOR SELECT
    TO anon
    USING (true);

-- 允许 service_role 完全访问（pipeline 用 service key）
CREATE POLICY "Allow service role full access"
    ON probability_changes
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
