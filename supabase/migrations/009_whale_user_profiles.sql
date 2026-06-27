-- Whale user profiles cache

CREATE TABLE IF NOT EXISTS whale_user_profiles (
    holder_address TEXT PRIMARY KEY,
    trades INTEGER,
    join_date TIMESTAMPTZ,
    last_fetched_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whale_user_profiles_last_fetched_at
    ON whale_user_profiles (last_fetched_at DESC);

ALTER TABLE whale_user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_whale_user_profiles"
    ON whale_user_profiles
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "service_full_whale_user_profiles"
    ON whale_user_profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
