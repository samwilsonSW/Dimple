-- Migration 020: Store per-hole scorecard data, plus two new inputs
--
-- Two things are happening here.
--
-- 1. Per-hole data was never stored. `hole_data` came in on the request, was
--    used to compute `round_stats`, and was discarded. That means no round can
--    ever be recomputed: when the strokes-gained model improves, only future
--    rounds benefit and history stays wrong. This table keeps the raw entries.
--
-- 2. Two new fields the model needs and cannot infer:
--
--    first_putt      How long the first putt was, as a bucket. "2 putts" alone
--                    is ambiguous — two from 40 feet is good play, two from 4
--                    feet is not. Without this, good putting and a good
--                    approach are indistinguishable, which is why two of the
--                    four round-history chips cannot be filled.
--
--    penalty_strokes Water, out of bounds, lost ball. Currently invisible, so
--                    those strokes get blamed on ball-striking. Worth roughly
--                    2-3 shots a round at a mid handicap.
--
-- See docs/SG_REBUILD.md for why these two and not others.

-- ── Per-hole entries ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS hole_scores (
    id BIGSERIAL PRIMARY KEY,
    round_id BIGINT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,

    hole_number INTEGER NOT NULL CHECK (hole_number BETWEEN 1 AND 18),
    par INTEGER NOT NULL CHECK (par BETWEEN 3 AND 5),
    yardage INTEGER,

    score INTEGER NOT NULL CHECK (score BETWEEN 1 AND 15),
    putts INTEGER NOT NULL DEFAULT 2 CHECK (putts BETWEEN 0 AND 10),
    fairway BOOLEAN,                    -- NULL on par 3s
    gir BOOLEAN,

    -- New. Both nullable: rounds logged before this migration, and holes the
    -- player skipped the question on, must stay valid.
    first_putt TEXT CHECK (first_putt IN ('tap_in', 'short', 'mid', 'long')),
    penalty_strokes INTEGER NOT NULL DEFAULT 0 CHECK (penalty_strokes BETWEEN 0 AND 9),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (round_id, hole_number)
);

CREATE INDEX IF NOT EXISTS idx_hole_scores_round_id ON hole_scores(round_id);
CREATE INDEX IF NOT EXISTS idx_hole_scores_user_id ON hole_scores(user_id);

COMMENT ON COLUMN hole_scores.first_putt IS
    'Distance bucket of the first putt: tap_in (<3ft), short (3-10ft), mid (10-25ft), long (25ft+). NULL if not recorded.';
COMMENT ON COLUMN hole_scores.penalty_strokes IS
    'Penalty strokes taken on the hole (water, OB, lost ball). Included in score.';

ALTER TABLE hole_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own hole scores"
    ON hole_scores FOR ALL
    USING (user_id = current_setting('app.current_user_id', true));

CREATE POLICY "Service role can access all hole scores"
    ON hole_scores FOR ALL TO service_role
    USING (true);

-- ── Round-level rollups ──────────────────────────────────────────────────────
-- Nullable rather than defaulted to 0: a round logged before this migration has
-- no penalty data, and that is different from a round with zero penalties.

ALTER TABLE round_stats ADD COLUMN IF NOT EXISTS total_penalty_strokes INTEGER;
ALTER TABLE round_stats ADD COLUMN IF NOT EXISTS avg_first_putt_ft NUMERIC(4, 1);

COMMENT ON COLUMN round_stats.total_penalty_strokes IS
    'Sum of penalty strokes across the round. NULL if the round predates collection.';
COMMENT ON COLUMN round_stats.avg_first_putt_ft IS
    'Mean representative first-putt distance in feet, from the hole buckets. NULL if unrecorded.';
