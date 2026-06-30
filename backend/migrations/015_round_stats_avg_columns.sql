-- Migration 015: add missing avg columns to round_stats
--
-- The LIVE round_stats table (created manually before migration 002) is missing
-- `avg_putts_per_hole` and `avg_score_to_par`, which calculate_round_stats writes
-- on every round submit. Without them the stats INSERT fails with PGRST204
-- ("Could not find the 'avg_putts_per_hole' column ... in the schema cache"),
-- so rounds save but come back with no stats ("Stats unavailable" in History).
--
-- Run this in the Supabase SQL editor.

ALTER TABLE round_stats
    ADD COLUMN IF NOT EXISTS avg_putts_per_hole NUMERIC(4, 2),
    ADD COLUMN IF NOT EXISTS avg_score_to_par   NUMERIC(4, 2);

-- Refresh PostgREST's schema cache so the new columns are immediately usable
-- (no backend restart needed).
NOTIFY pgrst, 'reload schema';
