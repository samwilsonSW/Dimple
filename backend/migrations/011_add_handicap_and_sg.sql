-- Migration 005: Add handicap_index to rounds, SG fields to shot_embeddings

-- 1. Add handicap_index to rounds table
ALTER TABLE rounds
ADD COLUMN IF NOT EXISTS handicap_index NUMERIC(4, 1) DEFAULT 0.0;

-- 2. Add SG fields to shot_embeddings
ALTER TABLE shot_embeddings
ADD COLUMN IF NOT EXISTS before_distance_yards INTEGER,
ADD COLUMN IF NOT EXISTS before_lie TEXT,
ADD COLUMN IF NOT EXISTS after_distance_yards INTEGER,
ADD COLUMN IF NOT EXISTS after_lie TEXT,
ADD COLUMN IF NOT EXISTS strokes_taken INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS sg_value NUMERIC(5, 2);

-- 3. Index for SG aggregation queries
CREATE INDEX IF NOT EXISTS idx_shot_embeddings_sg
ON shot_embeddings(user_id, sg_value);

-- 4. Index for lie-type filtering
CREATE INDEX IF NOT EXISTS idx_shot_embeddings_before_lie
ON shot_embeddings(before_lie);

-- 5. Update match_shots RPC to return SG fields
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
    club TEXT,
    distance INTEGER,
    narrative TEXT,
    before_distance_yards INTEGER,
    before_lie TEXT,
    after_distance_yards INTEGER,
    after_lie TEXT,
    strokes_taken INTEGER,
    sg_value NUMERIC,
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
        se.club,
        se.distance,
        se.narrative,
        se.before_distance_yards,
        se.before_lie,
        se.after_distance_yards,
        se.after_lie,
        se.strokes_taken,
        se.sg_value,
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM shot_embeddings se
    WHERE se.user_id = match_user_id
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
