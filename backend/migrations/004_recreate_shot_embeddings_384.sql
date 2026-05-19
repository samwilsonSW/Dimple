-- DROP old 1536-dim schema and recreate for 384-dim (all-MiniLM-L6-v2)

-- 1. Drop the old RPC function first (depends on table type)
DROP FUNCTION IF EXISTS match_shots(VECTOR(1536), TEXT, INT);

-- 2. Drop the old table (cascades indexes, policies)
DROP TABLE IF EXISTS shot_embeddings;

-- 3. Recreate shot_embeddings with VECTOR(384)
CREATE TABLE shot_embeddings (
    id BIGSERIAL PRIMARY KEY,
    shot_id TEXT NOT NULL,
    round_id BIGINT REFERENCES rounds(id),
    user_id TEXT NOT NULL,
    hole_number INTEGER,
    club TEXT,
    distance INTEGER,
    narrative TEXT,
    embedding VECTOR(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. HNSW index for fast similarity search (384-dim)
CREATE INDEX idx_shot_embeddings_vector
ON shot_embeddings USING hnsw (embedding vector_cosine_ops);

-- 5. Index for user-scoped queries
CREATE INDEX idx_shot_embeddings_user_id
ON shot_embeddings(user_id);

-- 6. Row Level Security (RLS)
ALTER TABLE shot_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own shot embeddings"
    ON shot_embeddings
    FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Service role can access all shot embeddings"
    ON shot_embeddings
    FOR ALL
    TO service_role
    USING (true);

-- 7. RPC function for cosine similarity search (384-dim)
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
        1 - (se.embedding <=> query_embedding) AS similarity
    FROM shot_embeddings se
    WHERE se.user_id = match_user_id
    ORDER BY se.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
