-- Supabase SQL: create late_markets table
-- Run in Supabase SQL Editor or via Postgres DSN migration.

CREATE TABLE IF NOT EXISTS late_markets (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id TEXT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    volume_usd DOUBLE PRECISION NOT NULL,
    liquidity_usd DOUBLE PRECISION,
    markets_count INTEGER,
    category TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE late_markets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous read"
    ON late_markets
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Allow service role full access"
    ON late_markets
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
