-- Migration 020: Conversation summary for extended context window
--
-- The coach chat endpoint sends the last 15 messages verbatim. For longer
-- conversations, older messages are summarized by a cheap LLM call and cached
-- here so the coach retains long-term context without re-summarizing every
-- request.
--
-- Run this in the Supabase SQL editor.

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS summarized_message_count INTEGER DEFAULT 0;

COMMENT ON COLUMN conversations.summary IS
    'LLM-generated bullet summary of messages older than the context window';
COMMENT ON COLUMN conversations.summarized_message_count IS
    'How many leading messages the summary covers (refresh when 10+ new messages age out)';

-- Service role writes summaries from the backend
GRANT UPDATE ON public.conversations TO service_role;
