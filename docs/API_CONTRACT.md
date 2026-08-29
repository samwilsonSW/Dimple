# Dimple API Contract

> **The score.** If it's not here, it doesn't exist. If code contradicts this, this wins.

---

## Version

`1.2.0` — matches `backend/app/main.py`

---

## Global Rules

| Rule | Example |
|------|---------|
| UUIDs lowercase | `550e8400-e29b-41d4-a716-446655440000` |
| Dates `YYYY-MM-DD` | `2026-08-13` |
| Handicap 0.0–54.0 | `13.2` |
| Putting = feet, else yards | `before_distance_yards: 8` (feet for putts) |
| Python **3.12 only** | `pydantic-core` fails to build on 3.14 (PyO3 max 3.13) |

---

## Shapes live in `openapi.json`

Field-level request/response schemas are **generated** from the Pydantic models
into [`openapi.json`](./openapi.json) — that file is authoritative for shapes.
Hand-transcribed schemas drift; generated ones cannot.

```bash
cd backend && python scripts/export_openapi.py     # regenerate after model changes
cd backend && python scripts/smoke_test.py         # fails if it is stale
```

This document carries what a schema cannot: semantics, error meanings, and the
risks below. The examples in each endpoint section are illustrative — when an
example and `openapi.json` disagree, the generated file wins.

---

## Endpoints

### Health

```
GET /health
→ {"status": "ok"}
```

---

### Ingest Round

```
POST /api/v1/rounds
```

**With API course:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-06-15",
  "course": {"name": "Pinehurst No. 2", "city": "Pinehurst", "state": "NC"},
  "handicap_index": 13.2,
  "course_id": "pinehurst-2",
  "tee_box": {"tee_name": "Blue", "rating": 74.9, "slope": 134},
  "hole_data": [{"hole_number": 1, "par": 4, "score": 5, "putts": 2, "fairway": false, "gir": false, "first_putt": "mid", "penalty_strokes": 0}],
  "total_score": 85,
  "total_putts": 32
}
```

**With manual course:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-08-06",
  "course": {"name": "Creek Course", "city": "Lubbock", "state": "TX"},
  "handicap_index": 13.2,
  "manual_course": {"holes": 18, "par_values": [4,4,3,4,5,4,4,3,4,4,4,3,4,5,4,4,3,4]},
  "hole_data": [{"hole_number": 1, "par": 4, "score": 5, "putts": 2, "fairway": false, "gir": false, "first_putt": "mid", "penalty_strokes": 0}],
  "total_score": 94,
  "total_putts": 36
}
```

**Rules:**
- `course_id` XOR `manual_course` — never both
- `manual_course` → no `shots`, no `tee_box`
- `hole_data` OR `shots` (or both)
- `hole_data[].first_putt` is one of `tap_in` (<3ft), `short` (3-10ft),
  `mid` (10-25ft), `long` (25ft+), or omitted. Putt count alone is ambiguous —
  two putts from 40 feet is good play, two from 4 feet is not — so without it
  putting and approach quality cannot be separated. Omitted is meaningful and
  is not the same as a short putt: it means unrecorded.
- `hole_data[].penalty_strokes` defaults to 0 and is **already included** in
  `score`. Do not add it on top.
- Per-hole entries are persisted to `hole_scores`, so rounds can be recomputed
  when the strokes-gained model changes. Failure to store them does not fail
  the request; the round and its stats still land.
- `manual_course.par_values` is the whole course; `strokes_over_under` and
  `avg_score_to_par` count only the holes present in `hole_data`, matched by
  `hole_number`. A front-nine round on an 18-hole manual course is scored
  against those nine pars.

**Response:**
```json
{
  "round_id": 42,
  "status": "success",
  "round_stats": {
    "total_score": 85,
    "sg_putting": -1.2,
    "sg_approach": -2.5,
    "gir_percentage": 0.278,
    "fairway_percentage": 0.5
  }
}
```

---

### Coach Chat

```
POST /api/v1/coach/chat
```

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "How can I work on my putting?",
  "conversation_id": 42,
  "round_id": 123
}
```

**Response:**
```json
{
  "conversation_id": 42,
  "message": {"role": "assistant", "content": "Based on your stats..."},
  "answer": "Your putting...",
  "confidence": 4,
  "key_insights": ["Putting: 36 putts/round"],
  "drill_recommendations": [
    {
      "priority": 1,
      "drill_name": "Ladder Drill",
      "focus_area": "Distance control",
      "steps": ["Putt to 10 feet", "Then 20, 30 and 40"],
      "instructions": "1. Putt to 10 feet 2. Then 20, 30 and 40",
      "expected_outcome": "All four inside three feet"
    }
  ]
}
```

`steps` is the drill broken into ordered steps. `instructions` is the same
content joined into one string, kept so a client built before 1.2.0 still
renders something. Prefer `steps`.

**Confidence scale** — derived from the data inventory server-side, not from the
model. It answers "how much data backs this answer", so it is known before the
LLM is called and is sent as the first streaming event.
- 1: 1-2 rounds (asks follow-up)
- 2: 3-5 rounds (early trends)
- 3: 5+ rounds, no shots (scorecard patterns)
- 4: With shot data (specific patterns)
- 5: Rich shot + trend data

**This endpoint cannot answer before the model finishes.** Cloudflare gives the
origin 100s to start responding, and a long reply exceeds it — the app gets a
524. It is kept for clients that predate 1.2.0; everything new should stream.

---

### Coach Chat (streaming)

```
POST /api/v1/coach/chat/stream
```

Same request body as `/coach/chat`. Responds with Server-Sent Events. The first
bytes go out before any database work, which is what stops Cloudflare's 100s
clock — a slow answer can no longer 524.

| Event | Payload | Notes |
|-------|---------|-------|
| `meta` | `{conversation_id, confidence}` | Once, as soon as the conversation exists |
| `delta` | `{text}` | Prose to append. Many of these. |
| `insight` | `{text}` | One completed insight |
| `drill` | `{index, priority, drill_name, focus_area, steps, instructions, expected_outcome}` | **Re-sent as fields arrive — upsert on `index`** |
| `done` | `{answer}` | Full prose, already persisted |
| `error` | `{detail}` | Terminal. Anything already streamed is still saved. |

Lines starting with `:` are keepalives; ignore them. A `drill` arrives partially
built — a card should paint its header and fill in steps as they stream.

Errors after the first byte arrive as an `error` event, not an HTTP status: the
headers are long gone by then. Clients must handle a 200 that fails midway.

---

### Coach Conversations

```
GET /api/v1/coach/conversations?user_id={uuid}&limit=10
→ {"conversations": [{"id": 42, "title": "Round at Rawls", "message_count": 8, "preview": "..."}]}
```

```
GET /api/v1/coach/conversations/{id}/messages?user_id={uuid}
→ {"conversation_id": 42, "messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

---

### Course Search

```
GET /api/v1/courses/search?q={query}&limit=10
→ {"courses": [{"id": "21027", "name": "The Rawls Course", "city": "Lubbock", "state": "TX", "holes": 18}]}
```

```
GET /api/v1/courses/{course_id}
→ {"course": {"id": "21027", "name": "...", "tee_data": {...}, "hole_data": {...}}}
```

---

### Round History

```
GET /api/v1/rounds?user_id={uuid}&limit=20
→ {"rounds": [{"round_id": 42, "round_date": "2026-06-15", "course": {...}, "total_score": 85, "round_stats": {...}}]}
```

---

## The coach wire format

The coach model answers in a line-tagged format, **not JSON**. Prose is the
default; a line starting with `@` is structure:

```
Off the tee is where you're losing it.

@insight Driver dispersion is 2x your 3-wood

@drill Gate Drill
@focus Driver face control
@step Place two tees just wider than your driver head
@win Ten clean swings before you move on
```

One line per tag; `@focus`/`@step`/`@win` attach to the `@drill` above them;
`priority` is order of appearance. Parsed by
`backend/app/services/coach_format.py`, which is also where the format
instructions handed to the model live — change both together or neither.

Why not JSON: it cannot be streamed (unreadable until the closing brace), one
bad brace threw away a whole paid response as a 502, and a quarter of the output
tokens were syntax. An unrecognised tag degrades to prose, so the worst case is
a stray line rather than a lost reply.

---

## Database Schema

**`rounds`**
- `id` BIGSERIAL PK
- `user_id` text (lowercase UUID)
- `round_date` date
- `course_name`, `course_city`, `course_state` text
- `handicap_index` numeric
- `reflection` text (optional)
- `course_id` text (optional, from API)
- `tee_name`, `tee_rating`, `tee_slope` (optional)
- `manual_course` jsonb (optional)
- `total_score`, `total_putts` int
- `created_at` timestamp

**`shots`**
- `id` BIGSERIAL PK
- `round_id` BIGINT FK
- `user_id` text
- `hole_number`, `shot_number` int
- `before_distance_yards`, `after_distance_yards` int
- `before_lie`, `after_lie` text
- `club` text
- `sg` numeric
- `embedding` vector(384)

**`round_stats`**
- `id` BIGSERIAL PK
- `round_id` BIGINT FK
- `user_id` text
- `total_score`, `total_putts` int
- `gir_count`, `gir_percentage` int/numeric
- `fairways_hit`, `fairways_possible`, `fairway_percentage` int/numeric
- `sg_putting`, `sg_approach` numeric
- `strokes_over_under` numeric
- `avg_putts_per_hole`, `avg_score_to_par` numeric
- `total_penalty_strokes` int, nullable — null means the round predates collection
- `avg_first_putt_ft` numeric, nullable — mean representative first-putt distance

**`hole_scores`** (migration 020)
- `id` BIGSERIAL PK
- `round_id` BIGINT FK, `user_id` text
- `hole_number`, `par`, `yardage`, `score`, `putts` int
- `fairway`, `gir` boolean, nullable
- `first_putt` text, nullable — `tap_in` | `short` | `mid` | `long`
- `penalty_strokes` int, default 0
- UNIQUE (`round_id`, `hole_number`)

**`courses`**
- `id` uuid PK
- `external_id` text unique
- `name`, `club_name`, `city`, `state`, `country` text
- `holes_count` int
- `tee_data`, `hole_data` jsonb

---

## Errors

| Code | Meaning |
|------|---------|
| 422 | Validation error (bad UUID, both `course_id` and `manual_course`, etc.) |
| 500 | Supabase or LLM failure |
| 404 | Conversation not found |

---

## Known Risks & Edge Cases

Landmines that have already cost real debugging time. Read before touching the
seam — this table is the reason it exists.

| Risk | Status / mitigation |
|------|---------------------|
| `match_shots` RPC is **case-sensitive** on `user_id` | Lowercase every UUID before sending. Uppercase fails silently — no error, just no matches. |
| Cloudflare 524s a slow `/coach/chat` | **Root cause of "couldn't reach the coach".** The API is behind Cloudflare, which allows the origin 100s to *start* responding. Reproduced 2026-08-29: a 125s reply returned HTTP 524, and the iOS error bubble showed it as unreachable. Fixed by `/coach/chat/stream` — first byte goes out before any DB work. The buffered endpoint still has this ceiling. |
| Coach latency | ~95s measured 2026-08-05, still true. Streaming hides it rather than removing it: prose starts in seconds. The part streaming cannot hide is `prepare_coach_turn` — ~12 sequential Supabase calls before the first token. **Anything adding a round-trip to `/coach/chat` is a taste decision — escalate it.** |
| "Couldn't reach the coach." is a generic title | `CoachChatView.swift` and `CoachChatScreen.tsx` show it for *every* send failure, including a 524 or a decode error. Read the second line of the bubble before believing it is a network problem. |
| Backend→Supabase intermittent timeout on `/coach/chat` | Mitigated 2026-07 by connection pooling + making the conversation verify non-fatal (`fa7e17d`). Watch for recurrence rather than assuming it's gone. |
| `GET /coach/conversations` and `/{id}/messages` require `user_id` | Missing → 422, not 500. Clients must always send it. |
| GolfCourseAPI rate limit (50 req/day) | Cache aggressively in the Supabase `courses` table. |
| Duplicate rounds on retry/submit | **Open.** No idempotency key. Fix is `client_round_id` + a unique constraint. |
| Migrations are applied **by hand** in the Supabase SQL editor | `backend/migrations/` being present does *not* mean it ran. Never assume; ask or check the live schema. |
| Forward references in `app/models/round.py` annotations | A class used in an annotation must be **defined above** its use, or import fails on Python < 3.14 (lazy annotations are 3.14+). Cost: the whole module failed to import on 3.12 from July until 2026-08-20. |
| Python 3.14 **not supported** | `pydantic-core` (via PyO3) fails to build on 3.14 (max supported: 3.13). **Use Python 3.12.** Cost: server wouldn't start on 2026-08-20 after `uv` picked up system Python 3.14. Fix: `uv python install 3.12 && uv venv --python 3.12 && uv sync`. |
| Embedding model download | **Fixed 2026-08-20.** `embeddings.py` used to build `SentenceTransformer` at module scope, so importing the app pulled ~90MB from HuggingFace and the server could not start without network access to huggingface.co. Now loads lazily via `get_model()`. Do not move it back to module scope. |
| Dependency pins are load-bearing for `openapi.json` | The schema is emitted by pydantic, so a different pydantic version produces a slightly different file and the freshness check reports phantom drift. Always run tooling through `uv run`, never a hand-rolled venv. |
| `requirements.txt` is **generated** | It is exported from `uv.lock`. Editing it by hand is silently discarded on the next export — change `pyproject.toml` and re-run `uv lock`. |

---

## Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-05-22 | 0.5.0 | Reflections, SG aggregation, score variance |
| 2026-06-16 | 0.6.0 | Course search, simple scorecard mode (`hole_data`), `courses` table |
| 2026-06-29 | 0.6.0 | `round_id` is Int (BIGSERIAL) not String; `round_stats` is an array in history; added `avg_putts_per_hole`, `avg_score_to_par` |
| 2026-07-14 | 0.7.0 | Replaced `/coach/ask` with `/coach/chat`. Added `/coach/conversations` and `/{id}/messages`. Removed the 25+ handicap gate. Data-source-aware prompts. |
| 2026-08-06 | 0.7.1 | Added `manual_course` to `POST /rounds` (migration 019). Mutually exclusive with `course_id`; rejects `shots`. |
| 2026-08-21 | 0.7.1 | Fix: `manual_course` stats summed all par values regardless of holes played, so partial rounds reported a wrong `strokes_over_under`. Now matched by `hole_number`. |
| 2026-08-29 | 1.2.0 | Added `POST /coach/chat/stream` (SSE). The coach LLM no longer emits JSON — it writes the line-tagged format above, parsed by `coach_format.py`. `drill_recommendations` gains `steps`; `instructions` stays as a joined string for older clients. `confidence` is now computed from the data inventory rather than self-reported by the model, and conversation titling moved off the request path. |
| 2026-08-28 | 1.1.0 | Added `first_putt` and `penalty_strokes` to `hole_data`, and the `hole_scores` table (migration 020). Per-hole data is now persisted rather than discarded, so rounds can be recomputed. `round_stats` gains `total_penalty_strokes` and `avg_first_putt_ft`. Both new fields are recorded but not yet used in the SG figures — see `docs/SG_REBUILD.md`. |

`0.7.2` is proposed on `feature/coach-context-memory` (conversation summary,
migration 020) and is **not** merged — see PR #16.

---

*Owner: whoever touches the backend. Update this first, then the code.*
