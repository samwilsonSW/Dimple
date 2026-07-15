-- Migration 017: Fix round_stats.round_id type mismatch and add conversations/messages tables

-- Step 1: Add UUID column to round_stats
ALTER TABLE round_stats ADD COLUMN round_id_uuid UUID;

-- Step 2: Update existing round_stats rows with correct UUID mappings
-- Round 102 -> cd49e74e-34a7-4b05-a29a-c8e953907f6a
UPDATE round_stats SET round_id_uuid = 'cd49e74e-34a7-4b05-a29a-c8e953907f6a'::UUID WHERE round_id = 102;

-- Round 101 -> 1efa01b5-e964-4895-a6f8-01a86941e30a
UPDATE round_stats SET round_id_uuid = '1efa01b5-e964-4895-a6f8-01a86941e30a'::UUID WHERE round_id = 101;

-- Step 3: Drop old integer round_id column
ALTER TABLE round_stats DROP COLUMN round_id;

-- Step 4: Rename new column to round_id
ALTER TABLE round_stats RENAME COLUMN round_id_uuid TO round_id;

-- Step 5: Add foreign key constraint
ALTER TABLE round_stats ADD CONSTRAINT fk_round_stats_rounds 
    FOREIGN KEY (round_id) REFERENCES rounds(id) ON DELETE CASCADE;

-- Step 6: Create index on new round_id
CREATE INDEX idx_round_stats_round_id ON round_stats(round_id);

-- Step 7: Create conversations table
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    round_id UUID REFERENCES rounds(id) ON DELETE SET NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 8: Create messages table
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 9: Create indexes
CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at ASC);

-- Step 10: Grant permissions to service_role
GRANT SELECT, INSERT, UPDATE ON public.conversations TO service_role;
GRANT SELECT, INSERT ON public.messages TO service_role;
GRANT USAGE, SELECT ON SEQUENCE conversations_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE messages_id_seq TO service_role;
