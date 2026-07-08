-- Migration 007: Update schema for single-letter lie/club codes

-- Lie codes stored as single letters in API, expanded to full words in DB
-- T = tee, F = fairway, R = rough, B = bunker (sand), G = green
-- Club codes: D, 3W, 5W, H, 3-9, G=gap, L=lob, P=putter

-- 1. Drop and recreate shot_embeddings with updated schema
DROP TABLE IF EXISTS shot_embeddings CASCADE;

CREATE TABLE shot_embeddings (
    id BIGSERIAL PRIMARY KEY,
    shot_id TEXT NOT NULL,
    round_id BIGINT REFERENCES rounds(id),
    user_id TEXT NOT NULL,
    hole_number INTEGER NOT NULL,
    shot_number INTEGER NOT NULL,

    -- Raw user input (codes)
    before_distance_yards INTEGER NOT NULL,
    before_lie_code TEXT NOT NULL CHECK (before_lie_code IN ('T', 'F', 'R', 'B', 'G')),
    club_code TEXT NOT NULL CHECK (club_code IN ('D', '3W', '5W', 'H', '3', '4', '5', '6', '7', '8', '9', 'G', 'L', 'P')),

    -- Expanded values for queries
    before_lie TEXT NOT NULL,
    club TEXT NOT NULL,

    -- After-state (from next shot input)
    after_distance_yards INTEGER,
    after_lie_code TEXT CHECK (after_lie_code IN ('T', 'F', 'R', 'B', 'G', 'HOLE')),
    after_lie TEXT,

    -- Strokes
    strokes_taken INTEGER DEFAULT 1,

    -- Calculated SG vs player's handicap baseline
    sg_value NUMERIC(5, 2),

    -- Auto-generated narrative for embedding
    narrative TEXT NOT NULL,

    -- Vector embedding
    embedding VECTOR(384),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexes
CREATE INDEX idx_shot_embeddings_vector
ON shot_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_shot_embeddings_user_id
ON shot_embeddings(user_id);

CREATE INDEX idx_shot_embeddings_sg
ON shot_embeddings(user_id, sg_value);

CREATE INDEX idx_shot_embeddings_before_lie
ON shot_embeddings(before_lie);

CREATE INDEX idx_shot_embeddings_hole
ON shot_embeddings(round_id, hole_number, shot_number);

-- 3. Row Level Security
ALTER TABLE shot_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own shot embeddings"
    ON shot_embeddings
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Service role can access all shot_embeddings"
    ON shot_embeddings
    FOR ALL
    TO service_role
    USING (true);

-- 4. Updated match_shots RPC
DROP FUNCTION IF EXISTS match_shots(VECTOR(384), TEXT, INT);

CREATE OR REPLACE FUNCTION match_shots(
    query_embedding VECTOR(384),
    match_user_id TEXT,
    match_count INT DEFAULT 5
)
RETURNS TABLE(
    shot_id TEXT,
    round_id BIGINT,
    user_id TEXT,
    hole_number INTEGER,
    shot_number INTEGER,
    before_distance_yards INTEGER,
    before_lie_code TEXT,
    before_lie TEXT,
    club_code TEXT,
    club TEXT,
    after_distance_yards INTEGER,
    after_lie_code TEXT,
    after_lie TEXT,
    strokes_taken INTEGER,
    sg_value NUMERIC,
    narrative TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        se.shot_id,
        se.round_id,
        se.user_id,
        se.hole_number,
        se.shot_number,
        se.before_distance_yards,
        se.before_lie_code,
        se.before_lie,
        se.club_code,
        se.club,
        se.after_distance_yards,
        se.after_lie_code,
        se.after_lie,
        se.strokes_taken,
        se.sg_value,
        se.narrative,
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM shot_embeddings se
    WHERE se.user_id = match_user_id
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
