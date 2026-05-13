-- Run this in your Supabase SQL Editor
-- Creates the rounds table with proper structure

CREATE TABLE IF NOT EXISTS rounds (
    id BIGSERIAL PRIMARY KEY,
    round_id UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    user_id TEXT NOT NULL,
    round_date DATE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    
    -- Course info (JSON for flexibility)
    course JSONB DEFAULT '{"name": "Unknown Course"}'::jsonb,
    
    -- Player info
    player JSONB DEFAULT '{}'::jsonb,
    
    -- Holes array (each hole contains shots array)
    holes JSONB DEFAULT '[]'::jsonb,
    
    -- Computed stats
    total_score INTEGER,
    total_putts INTEGER,
    fairways_hit INTEGER,
    greens_in_regulation INTEGER,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_rounds_user_id ON rounds(user_id);
CREATE INDEX IF NOT EXISTS idx_rounds_round_date ON rounds(round_date);
CREATE INDEX IF NOT EXISTS idx_rounds_start_time ON rounds(start_time DESC);

-- Row Level Security (RLS) — users can only see their own rounds
ALTER TABLE rounds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own rounds"
    ON rounds
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

-- For the backend service key (bypasses RLS), this policy allows everything
CREATE POLICY "Service role can access all rounds"
    ON rounds
    FOR ALL
    TO service_role
    USING (true);

-- Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_rounds_updated_at ON rounds;
CREATE TRIGGER update_rounds_updated_at
    BEFORE UPDATE ON rounds
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
