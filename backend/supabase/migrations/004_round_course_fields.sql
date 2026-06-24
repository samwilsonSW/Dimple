-- Add course-related fields to rounds table
-- Links rounds to cached course data and stores tee/hole info

-- Add course reference and tee selection
alter table rounds
    add column if not exists course_id uuid references courses(id),
    add column if not exists tee_box jsonb,           -- { tee_name, rating, slope }
    add column if not exists hole_data jsonb,         -- Array of per-hole results
    add column if not exists total_score int,
    add column if not exists total_putts int;

-- hole_data schema (per hole):
-- [
--   {
--     "hole_number": 1,
--     "par": 4,
--     "yardage": 420,
--     "score": 5,
--     "putts": 2,
--     "fairway": true,
--     "gir": false
--   },
--   ...
-- ]

-- Index for course lookups
CREATE INDEX IF NOT EXISTS idx_rounds_course_id ON rounds(course_id);
