-- Supabase SQL: 创建 market_analysis 表

CREATE TABLE IF NOT EXISTS market_analysis (
    slug TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    sides JSONB NOT NULL
);

-- RLS
ALTER TABLE market_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous read"
    ON market_analysis
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Allow service role full access"
    ON market_analysis
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
