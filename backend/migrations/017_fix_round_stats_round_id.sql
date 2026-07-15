-- Migration 017: Fix round_stats.round_id type to match rounds.id (BIGINT)
-- 
-- Problem: round_stats.round_id was created as BIGINT in migration 002,
-- but rounds.id is also BIGINT. The previous migration attempt tried to 
-- change round_stats.round_id to UUID which doesn't match rounds.id.
--
-- This migration ensures consistency: both are BIGINT.

-- Step 1: Ensure round_stats.round_id is BIGINT (it should already be)
-- This is a no-op if already BIGINT, but ensures consistency
ALTER TABLE round_stats ALTER COLUMN round_id TYPE BIGINT;

-- Step 2: Add explicit foreign key constraint if not exists
-- First drop if exists to avoid errors
ALTER TABLE round_stats DROP CONSTRAINT IF EXISTS fk_round_stats_rounds;

-- Add the foreign key constraint
ALTER TABLE round_stats ADD CONSTRAINT fk_round_stats_rounds 
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE;

-- Step 3: Create conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    round_id BIGINT REFERENCES rounds(id) ON DELETE SET NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 4: Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 5: Create indexes
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at ASC);

-- Step 6: Grant permissions to service_role
GRANT SELECT, INSERT, UPDATE ON public.conversations TO service_role;
GRANT SELECT, INSERT ON public.messages TO service_role;
GRANT USAGE, SELECT ON SEQUENCE conversations_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE messages_id_seq TO service_role;
