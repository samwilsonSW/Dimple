-- Migration 008: Add round reflection field

-- Player-written qualitative summary of their round
-- Used by AI coach for context alongside quantitative SG data
ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS reflection TEXT;

-- Index for searching reflections (if we want to retrieve by reflection content later)
CREATE INDEX IF NOT EXISTS idx_rounds_reflection
ON rounds(user_id, round_date)
WHERE reflection IS NOT NULL;

COMMENT ON COLUMN rounds.reflection IS 'Player 3-5 sentence reflection: what stood out, good/bad, tendencies';
