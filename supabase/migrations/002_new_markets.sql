-- Supabase SQL: 创建 new_markets 表
-- 在 Supabase Dashboard → SQL Editor 中执行

CREATE TABLE IF NOT EXISTS new_markets (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    question TEXT NOT NULL,
    url TEXT NOT NULL,
    ai_analysis JSONB,
    created_at TIMESTAMPTZ,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    batch_id TEXT
);

-- RLS: 开启行级安全
ALTER TABLE new_markets ENABLE ROW LEVEL SECURITY;

-- 允许匿名用户只读（前端用 anon key）
CREATE POLICY "Allow anonymous read"
    ON new_markets
    FOR SELECT
    TO anon
    USING (true);

-- 允许 service_role 完全访问（pipeline 用 service key）
CREATE POLICY "Allow service role full access"
    ON new_markets
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
