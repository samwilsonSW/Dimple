-- Migration 018: Ensure conversations.title exists and add title generation tracking
-- 
-- The conversations table was created in migration 017 with a title column.
-- This migration ensures it's properly set up for auto-title generation.

-- Step 1: Ensure title column exists (idempotent — no-op if already there)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'conversations' AND column_name = 'title'
    ) THEN
        ALTER TABLE conversations ADD COLUMN title TEXT;
    END IF;
END $$;

-- Step 2: Add index for finding untitled conversations efficiently
CREATE INDEX IF NOT EXISTS idx_conversations_untitled 
    ON conversations(title, created_at) 
    WHERE title IS NULL OR title = 'Coach Chat';

-- Step 3: Grant update permission on conversations to service_role
GRANT UPDATE ON public.conversations TO service_role;
