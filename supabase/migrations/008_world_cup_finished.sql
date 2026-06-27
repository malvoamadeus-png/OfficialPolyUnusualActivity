-- Finished World Cup events + profitable address results

CREATE TABLE IF NOT EXISTS world_cup_finished_events (
    event_slug TEXT PRIMARY KEY,
    event_id TEXT,
    event_title TEXT NOT NULL,
    event_end_time TIMESTAMPTZ NOT NULL,
    event_url TEXT NOT NULL,
    markets_scanned INTEGER NOT NULL DEFAULT 0,
    results_count INTEGER NOT NULL DEFAULT 0,
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_world_cup_finished_events_end_time
    ON world_cup_finished_events (event_end_time DESC);

CREATE TABLE IF NOT EXISTS world_cup_finished_positions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_slug TEXT NOT NULL,
    event_title TEXT NOT NULL,
    event_end_time TIMESTAMPTZ NOT NULL,
    event_url TEXT NOT NULL,
    board_type TEXT NOT NULL,
    market_slug TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    market_question TEXT NOT NULL,
    market_label TEXT NOT NULL,
    outcome_name TEXT,
    address TEXT NOT NULL,
    bet_amount DOUBLE PRECISION,
    profit_amount DOUBLE PRECISION NOT NULL,
    position_closed_at TIMESTAMPTZ,
    scanned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (event_slug, market_slug, address, market_label)
);

CREATE INDEX IF NOT EXISTS idx_world_cup_finished_positions_end_time
    ON world_cup_finished_positions (event_end_time DESC);

CREATE INDEX IF NOT EXISTS idx_world_cup_finished_positions_profit
    ON world_cup_finished_positions (profit_amount DESC);

CREATE INDEX IF NOT EXISTS idx_world_cup_finished_positions_event_slug
    ON world_cup_finished_positions (event_slug);

ALTER TABLE world_cup_finished_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE world_cup_finished_positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_world_cup_finished_events"
    ON world_cup_finished_events
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "service_full_world_cup_finished_events"
    ON world_cup_finished_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "anon_read_world_cup_finished_positions"
    ON world_cup_finished_positions
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "service_full_world_cup_finished_positions"
    ON world_cup_finished_positions
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
