-- Migration 021: Add sg_short and sg_driving to round_stats
--
-- The four-category strokes-gained split (G/P/F/A) requires two new columns.
-- The old sg_putting and sg_approach remain; sg_short and sg_driving are new
-- and nullable so rounds logged before this migration stay valid.

ALTER TABLE round_stats ADD COLUMN IF NOT EXISTS sg_short NUMERIC(5, 2);
ALTER TABLE round_stats ADD COLUMN IF NOT EXISTS sg_driving NUMERIC(5, 2);

COMMENT ON COLUMN round_stats.sg_short IS
    'Strokes gained: short game (chips, pitches, bunker shots around the green). NULL for rounds logged before the four-category split.';
COMMENT ON COLUMN round_stats.sg_driving IS
    'Strokes gained: driving (tee shots on par 4s and par 5s). NULL for rounds logged before the four-category split.';
