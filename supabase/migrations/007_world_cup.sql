-- World Cup match boards + address metrics cache

CREATE TABLE IF NOT EXISTS world_cup_match_boards (
    event_slug TEXT PRIMARY KEY,
    event_title TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    event_url TEXT NOT NULL,
    boards_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_world_cup_match_boards_start_time
    ON world_cup_match_boards (start_time ASC);

CREATE TABLE IF NOT EXISTS world_cup_address_metrics (
    address TEXT PRIMARY KEY,
    address_age_days DOUBLE PRECISION,
    total_pnl DOUBLE PRECISION,
    pnl_7d DOUBLE PRECISION,
    pnl_30d DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    snapshot_utc TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    details_json JSONB
);

ALTER TABLE world_cup_match_boards ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_cup_address_metrics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_world_cup_match_boards"
    ON world_cup_match_boards
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "service_full_world_cup_match_boards"
    ON world_cup_match_boards
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "anon_read_world_cup_address_metrics"
    ON world_cup_address_metrics
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "service_full_world_cup_address_metrics"
    ON world_cup_address_metrics
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
