-- Migration 001: Create rounds table (base table)
-- This was originally created manually in Supabase; migrated to SQL for reproducibility.

CREATE TABLE IF NOT EXISTS rounds (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    round_date DATE NOT NULL,
    course JSONB NOT NULL,              -- { name, city, state }
    handicap_index NUMERIC(4, 1) DEFAULT 0.0,
    reflection TEXT,                    -- Player's qualitative summary
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rounds_user_id ON rounds(user_id);
CREATE INDEX IF NOT EXISTS idx_rounds_round_date ON rounds(round_date);
CREATE INDEX IF NOT EXISTS idx_rounds_user_date ON rounds(user_id, round_date DESC);

-- Row Level Security
ALTER TABLE rounds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own rounds"
    ON rounds FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Service role can access all rounds"
    ON rounds FOR ALL TO service_role
    USING (true);
