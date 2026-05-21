-- Migration 006: Redesign shot input — structured data replaces narrative

-- The narrative field is no longer the source of truth.
-- We now collect structured data from the user:
--   - before_distance_yards (yards to pin before shot)
--   - before_lie (F/R/B/G)
--   - club (D/H/3W/5W/3/4/5/6/7/8/9/G/L/P)
--   - after_distance_yards (yards to pin after shot — from next shot input)
--   - after_lie (F/R/B/G — from next shot input)
--   - strokes_taken (1 for normal, 2+ for penalties, putt count for putting)

-- 1. Drop and recreate shot_embeddings with new schema
DROP TABLE IF EXISTS shot_embeddings CASCADE;

CREATE TABLE shot_embeddings (
    id BIGSERIAL PRIMARY KEY,
    shot_id TEXT NOT NULL,
    round_id BIGINT REFERENCES rounds(id),
    user_id TEXT NOT NULL,
    hole_number INTEGER NOT NULL,
    shot_number INTEGER NOT NULL,  -- 1 = tee shot, 2 = approach, etc.

    -- Input from user
    before_distance_yards INTEGER NOT NULL,
    before_lie TEXT NOT NULL CHECK (before_lie IN ('tee', 'fairway', 'rough', 'sand', 'green')),
    club TEXT NOT NULL,

    -- Derived from next shot (or 0 if holed)
    after_distance_yards INTEGER,
    after_lie TEXT CHECK (after_lie IN ('fairway', 'rough', 'sand', 'green', 'hole')),

    -- Strokes taken on this shot
    strokes_taken INTEGER DEFAULT 1,

    -- Calculated SG vs player's handicap baseline
    sg_value NUMERIC(5, 2),

    -- Auto-generated narrative for embedding/retrieval
    narrative TEXT NOT NULL,

    -- Vector embedding of the narrative
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
    before_lie TEXT,
    club TEXT,
    after_distance_yards INTEGER,
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
        se.before_lie,
        se.club,
        se.after_distance_yards,
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

-- 5. Helper function: generate narrative from structured data
-- This can be called from the backend or as a trigger
CREATE OR REPLACE FUNCTION generate_shot_narrative(
    p_before_distance INTEGER,
    p_before_lie TEXT,
    p_club TEXT,
    p_after_distance INTEGER,
    p_after_lie TEXT,
    p_strokes_taken INTEGER
)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_narrative TEXT;
    v_lie_phrase TEXT;
    v_result_phrase TEXT;
BEGIN
    -- Map lie to phrase
    v_lie_phrase := CASE p_before_lie
        WHEN 'tee' THEN 'from the tee'
        WHEN 'fairway' THEN 'from the fairway'
        WHEN 'rough' THEN 'from the rough'
        WHEN 'sand' THEN 'from the bunker'
        WHEN 'green' THEN 'on the green'
        ELSE 'from ' || p_before_lie
    END;

    -- Map result to phrase
    IF p_after_lie = 'hole' THEN
        v_result_phrase := 'holed it';
    ELSIF p_after_lie = 'green' THEN
        v_result_phrase := 'to ' || p_after_distance || ' feet on the green';
    ELSIF p_after_distance IS NOT NULL THEN
        v_result_phrase := 'to ' || p_after_distance || ' yards in the ' || p_after_lie;
    ELSE
        v_result_phrase := 'result unknown';
    END IF;

    -- Build narrative
    v_narrative := p_club || ' ' || p_before_distance || ' yards ' || v_lie_phrase || ', ' || v_result_phrase;

    -- Add penalty note
    IF p_strokes_taken > 1 THEN
        v_narrative := v_narrative || ' (penalty: ' || p_strokes_taken || ' strokes)';
    END IF;

    RETURN v_narrative;
END;
$$;
