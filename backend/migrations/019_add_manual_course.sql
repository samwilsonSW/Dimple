-- Migration 019: Support manually entered courses
-- Adds manual_course JSONB column to rounds table for fallback course entry

ALTER TABLE rounds ADD COLUMN manual_course JSONB NULL;

-- Add index for filtering manual vs API courses (analytics)
CREATE INDEX idx_rounds_manual_course ON rounds((manual_course IS NOT NULL));

-- Add comment for documentation
COMMENT ON COLUMN rounds.manual_course IS 'User-entered course data when course is not in GolfCourseAPI.com. Contains holes, par_values, and optional tee info.';
