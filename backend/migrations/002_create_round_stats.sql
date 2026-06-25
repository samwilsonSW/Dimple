-- Migration 002: Create round_stats table
-- Stores calculated statistics for each round (SG, GIR%, fairway%, etc.)

CREATE TABLE IF NOT EXISTS round_stats (
    id BIGSERIAL PRIMARY KEY,
    round_id BIGINT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    
    -- Basic stats
    total_score INTEGER,
    total_putts INTEGER,
    
    -- Greens in regulation
    gir_count INTEGER,
    gir_percentage NUMERIC(5, 3),
    
    -- Fairways
    fairways_hit INTEGER,
    fairways_possible INTEGER,
    fairway_percentage NUMERIC(5, 3),
    
    -- Strokes Gained
    sg_putting NUMERIC(5, 2),
    sg_approach NUMERIC(5, 2),
    
    -- Performance vs expectation
    strokes_over_under NUMERIC(5, 2),
    
    -- Averages
    avg_putts_per_hole NUMERIC(4, 2),
    avg_score_to_par NUMERIC(4, 2),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_round_stats_round_id ON round_stats(round_id);
CREATE INDEX IF NOT EXISTS idx_round_stats_user_id ON round_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_round_stats_created ON round_stats(created_at DESC);

-- Row Level Security
ALTER TABLE round_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own round stats"
    ON round_stats FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Service role can access all round_stats"
    ON round_stats FOR ALL TO service_role
    USING (true);
