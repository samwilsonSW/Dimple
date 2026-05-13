-- Enable pgvector extension for future RAG/embedding support
-- Run this in Supabase SQL Editor

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Future: Create table for shot embeddings
-- CREATE TABLE IF NOT EXISTS shot_embeddings (
--     id BIGSERIAL PRIMARY KEY,
--     shot_id TEXT NOT NULL,
--     round_id UUID REFERENCES rounds(round_id),
--     user_id TEXT NOT NULL,
--     embedding VECTOR(1536),  -- OpenAI text-embedding-3-small
--     content TEXT,  -- The text representation of the shot
--     created_at TIMESTAMPTZ DEFAULT NOW()
-- );

-- Future: Create similarity search index
-- CREATE INDEX ON shot_embeddings USING ivfflat (embedding vector_cosine_ops);
