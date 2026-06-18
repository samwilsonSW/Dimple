# Dimple API Contract

> **Owner:** Kanary (OpenClaw)  
> **Status:** Living document — versioned with the backend  
> **Rule:** If it's not in this contract, it doesn't exist. If it contradicts code, this contract wins (file a bug).

---

## Version

**API Version:** `0.6.0` (matches `backend/app/main.py`)

---

## Global Rules

### UUIDs
- **ALL `user_id` values are lowercase UUID strings.**
- Example: `550e8400-e29b-41d4-a716-446655440000` ✅
- Counter-example: `550E8400-E29B-41D4-A716-446655440000` ❌ — will fail `match_shots` RPC (case-sensitive)

### Dates
- `round_date` format: `YYYY-MM-DD` (ISO 8601 date only, no time component)

### Numbers
- `handicap_index`: float, 0.0–54.0. Stored as provided; backend handles 25+ with fundamentals redirect.
- Distances: yards (int) for all shots except putting — putting uses feet for `before_distance_yards`.

### Nullability
- Fields marked `Optional` may be omitted or set to `null`.
- Fields without `Optional` are required and will 422 if missing.

---

## Endpoints

### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "ok"
}
```

**Use:** Simulator smoke test, CI gate.

---

### Ingest Round

```
POST /api/v1/rounds
```

**Request Body:** `RoundPayload`

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-06-15",
  "course": {
    "name": "Pinehurst No. 2",
    "city": "Pinehurst",
    "state": "NC"
  },
  "handicap_index": 13.2,
  "reflection": "Driver was wild today. Short game saved me.",
  "course_id": "pinehurst-2",
  "tee_box": {
    "tee_name": "Blue",
    "rating": 74.9,
    "slope": 134
  },
  "hole_data": [
    {
      "hole_number": 1,
      "par": 4,
      "yardage": 402,
      "score": 5,
      "putts": 2,
      "fairway": false,
      "gir": false
    }
  ],
  "total_score": 85,
  "total_putts": 32,
  "shots": [
    {
      "shot_id": "hole1-shot1",
      "hole_number": 1,
      "shot_number": 1,
      "before_distance_yards": 402,
      "before_lie": "T",
      "club": "D",
      "after_distance_yards": 145,
      "after_lie": "R",
      "strokes_taken": 1
    }
  ]
}
```

**Field Rules:**
- Either `shots` (full shot-by-shot) OR `hole_data` (simple scorecard) must be provided. Both may be provided.
- `reflection`: optional, max ~500 chars. 3-5 sentences about the round.
- `course_id`: optional. If provided, links to cached course from `/courses/search`.
- `hole_data`: simple scorecard mode. Per-hole: score, putts, fairway (bool), GIR (bool).

**Response:**
```json
{
  "round_id": "uuid-of-round",
  "shots_ingested": 87,
  "shots_with_sg": 82,
  "handicap_index": 13.2,
  "reflection_saved": true,
  "status": "success"
}
```

**Errors:**
- `500` — Supabase insert failed or embedding failure
- `422` — Validation error (invalid lie code, club code, etc.)

---

### Coach Ask (RAG)

```
POST /api/v1/coach/ask
```

**Request Body:** `CoachQuery`

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "Why am I missing so many fairways?"
}
```

**Response:** `CoachResponse`

```json
{
  "answer": "Your driver is costing you 2.3 strokes per round...",
  "confidence": 4,
  "key_insights": [
    "Driving SG: -1.2 over last 5 rounds",
    "Missed fairways cluster on holes 3, 7, 12 (all dogleg left)"
  ],
  "drill_recommendations": [
    {
      "priority": 1,
      "focus_area": "driver accuracy",
      "drill_name": "Alignment Stick Gate",
      "instructions": "Place two alignment sticks 3 feet apart, 10 yards ahead. Hit 10 drivers through the gate.",
      "expected_outcome": "8/10 drives through the gate"
    }
  ],
  "context": [
    {
      "shot_id": "...",
      "narrative": "Driver: 402 yards to pin, tee shot → to 145 yards to pin, in rough",
      "sg_value": -0.45,
      ...
    }
  ]
}
```

**Special Behavior:**
- If player's most recent `handicap_index >= 25`, returns fundamentals redirect (no LLM call):
  - Answer focuses on: consistent contact, basic chipping, two-putting
  - Confidence: 5
  - Drills: 7-Iron Consistency, Chip-and-Putt

**Errors:**
- `500` — Embedding failure
- `502` — Supabase RPC failure or LLM generation failure

---

### Course Search

```
GET /api/v1/courses/search?q={query}&limit={limit}
```

**Query Parameters:**
- `q` (required, min 2 chars): Course name search string
- `limit` (optional, default 10, max 20): Max results

**Response:**
```json
{
  "query": "Rawls",
  "count": 3,
  "courses": [
    {
      "id": "21027",
      "name": "The Rawls Course At Texas Tech",
      "club_name": "The Rawls Course At Texas Tech",
      "city": "Lubbock",
      "state": "TX",
      "country": "United States",
      "holes_count": 18
    },
    {
      "id": "24982",
      "name": "Club At Rawls Creek, The",
      "club_name": "Club At Rawls Creek, The",
      "city": "Columbia",
      "state": "SC",
      "country": "United States",
      "holes_count": 18
    }
  ]
}
```

**Note:** Course `id` from this response is used as `course_id` in `RoundPayload`.

---

### Course Details

```
GET /api/v1/courses/{course_id}
```

**Response:**
```json
{
  "source": "api",
  "course": {
    "id": "21027",
    "name": "The Rawls Course At Texas Tech",
    "club_name": "The Rawls Course At Texas Tech",
    "city": "Lubbock",
    "state": "TX",
    "country": "United States",
    "holes_count": 18,
    "tee_data": [
      {
        "tee_id": "female_black",
        "tee_name": "Black",
        "gender": "female",
        "length": 7307,
        "par": 72,
        "slope": 148,
        "rating": 81.3
      },
      {
        "tee_id": "female_red",
        "tee_name": "Red",
        "gender": "female",
        "length": 6825,
        "par": 72,
        "slope": 142,
        "rating": 78.6
      },
      {
        "tee_id": "female_white",
        "tee_name": "White",
        "gender": "female",
        "length": 6270,
        "par": 72,
        "slope": 136,
        "rating": 75.5
      },
      {
        "tee_id": "female_gold",
        "tee_name": "Gold",
        "gender": "female",
        "length": 5493,
        "par": 72,
        "slope": 115,
        "rating": 70.5
      }
    ],
    "hole_data": [
      {
        "hole_number": 1,
        "par": 4,
        "yardage": 368,
        "handicap": 10
      },
      {
        "hole_number": 2,
        "par": 5,
        "yardage": 521,
        "handicap": 18
      }
    ]
  }
}
```

**Notes:**
- `source` is `"cache"` if from Supabase, `"api"` if fetched live and cached.
- `tee_data` includes both `male` and `female` tees from the API. The `gender` field distinguishes them.
- `handicap` on holes is the hole handicap (1-18) for stroke allocation, not player handicap.

---

## Data Models

### ShotModel (Input)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shot_id` | string | ✅ | Client-generated unique ID for this shot |
| `hole_number` | int | ✅ | 1–18 |
| `shot_number` | int | ✅ | 1 = tee shot, 2 = approach, etc. |
| `before_distance_yards` | int | ✅ | Yards to pin (feet if on green) |
| `before_lie` | string | ✅ | `T`, `F`, `R`, `B`, `G` |
| `club` | string | ✅ | `D`, `3W`, `5W`, `H`, `3`–`9`, `G`, `L`, `P` |
| `after_distance_yards` | int | ❌ | Yards/feet to pin after shot |
| `after_lie` | string | ❌ | `T`, `F`, `R`, `B`, `G`, `HOLE` |
| `strokes_taken` | int | ❌ | Default 1. 2+ for penalties. For putting, = number of putts. |
| `narrative` | string | ❌ | Leave null — backend auto-generates |

**Lie Codes:**
- `T` = tee
- `F` = fairway
- `R` = rough
- `B` = bunker (sand)
- `G` = green

**Club Codes:**
- `D` = Driver
- `3W`, `5W` = 3-wood, 5-wood
- `H` = Hybrid
- `3`–`9` = Irons
- `G` = Gap wedge
- `L` = Lob wedge
- `P` = Putter

### HoleResult (Simple Scorecard)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `hole_number` | int | ✅ | 1–18 |
| `par` | int | ✅ | 3–5 |
| `yardage` | int | ❌ | Hole yardage |
| `score` | int | ✅ | Strokes taken |
| `putts` | int | ❌ | Default 2 |
| `fairway` | bool | ❌ | True = hit, False = missed, null = par 3 |
| `gir` | bool | ❌ | Green in regulation |

### TeeBox

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tee_name` | string | ✅ | e.g. "Blue", "White" |
| `rating` | float | ❌ | Course rating |
| `slope` | int | ❌ | Slope rating |

### RoundPayload (Input)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | Lowercase UUID |
| `round_date` | string | ✅ | `YYYY-MM-DD` |
| `course` | object | ✅ | `{ name, city, state }` |
| `handicap_index` | float | ✅ | 0.0–54.0 |
| `reflection` | string | ❌ | 3-5 sentence round reflection |
| `course_id` | string | ❌ | From `/courses/search` |
| `tee_box` | TeeBox | ❌ | Selected tees |
| `hole_data` | HoleResult[] | ❌ | Simple scorecard (alternative to shots) |
| `total_score` | int | ❌ | Total strokes |
| `total_putts` | int | ❌ | Total putts |
| `shots` | ShotModel[] | ❌ | Full shot-by-shot data |

### CoachQuery (Input)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | Lowercase UUID |
| `question` | string | ✅ | Player's question |

### CoachResponse (Output)

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Natural language coaching response |
| `confidence` | int | 1–5 (1=speculative, 5=data-backed) |
| `key_insights` | string[] | 2–4 bullet points |
| `drill_recommendations` | DrillRecommendation[] | Ordered by priority |
| `context` | object[] | Retrieved shots that informed the answer (debug) |

### DrillRecommendation

| Field | Type | Description |
|-------|------|-------------|
| `priority` | int | 1 = highest |
| `focus_area` | string | e.g. "driver accuracy" |
| `drill_name` | string | Name of drill |
| `instructions` | string | Step-by-step |
| `expected_outcome` | string | What success looks like |

---

## Database Schema (Supabase)

### Tables

**`rounds`**
- `id` (uuid, PK)
- `user_id` (text, lowercase UUID)
- `round_date` (date)
- `course` (jsonb)
- `handicap_index` (float)
- `reflection` (text, nullable)
- `created_at` (timestamp)

**`shot_embeddings`**
- `id` (uuid, PK)
- `shot_id` (text)
- `round_id` (uuid, FK → rounds)
- `user_id` (text, lowercase UUID)
- `hole_number` (int)
- `shot_number` (int)
- `before_distance_yards` (int)
- `before_lie_code` (text)
- `before_lie` (text)
- `club_code` (text)
- `club` (text)
- `after_distance_yards` (int, nullable)
- `after_lie_code` (text, nullable)
- `after_lie` (text, nullable)
- `strokes_taken` (int)
- `narrative` (text)
- `sg_value` (float, nullable)
- `embedding` (vector(384))

**`courses`**
- `id` (uuid, PK)
- `external_id` (text, unique)
- `name` (text)
- `club_name` (text)
- `city` (text)
- `state` (text)
- `country` (text)
- `holes_count` (int)
- `tee_data` (jsonb)
- `hole_data` (jsonb)
- `created_at` (timestamp)

### RPC Functions

**`match_shots(query_embedding, match_user_id, match_count)`**
- Returns top-N similar shots for a user via cosine similarity
- `match_user_id` is **case-sensitive** — must be lowercase

---

## Known Risks & Edge Cases

| Risk | Mitigation | Owner |
|------|-----------|-------|
| `match_shots` case-sensitive on `user_id` | Frontend lowercases all UUIDs before sending | Claude Code |
| LLM thinking-mode latency > iOS 60s timeout | Monitor response times; consider streaming or async pattern | Kanary |
| Course API rate limit (50 req/day) | Cache aggressively in Supabase `courses` table | Kanary |
| 25+ handicap players get fundamentals redirect | Backend handles automatically; frontend shows same response shape | Kanary |

---

## Changelog

| Date | Version | Change |
|------|---------|--------|
| 2026-05-22 | 0.5.0 | Added reflections, SG aggregation, score variance |
| 2026-06-16 | 0.6.0 | Added course search, simple scorecard mode (`hole_data`), `courses` table |

---

*This contract is the score. Everyone reads it. Everyone plays from it.*
