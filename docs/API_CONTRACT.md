# Dimple API Contract

> **The score.** If it's not here, it doesn't exist. If code contradicts this, this wins.

---

## Version

`0.7.2` — matches `backend/app/main.py`

---

## Global Rules

| Rule | Example |
|------|---------|
| UUIDs lowercase | `550e8400-e29b-41d4-a716-446655440000` |
| Dates `YYYY-MM-DD` | `2026-08-13` |
| Handicap 0.0–54.0 | `13.2` |
| Putting = feet, else yards | `before_distance_yards: 8` (feet for putts) |

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
  "hole_data": [{"hole_number": 1, "par": 4, "score": 5, "putts": 2, "fairway": false, "gir": false}],
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
  "hole_data": [{"hole_number": 1, "par": 4, "score": 5, "putts": 2, "fairway": false, "gir": false}],
  "total_score": 94,
  "total_putts": 36
}
```

**Rules:**
- `course_id` XOR `manual_course` — never both
- `manual_course` → no `shots`, no `tee_box`
- `hole_data` OR `shots` (or both)

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
  "drill_recommendations": [{"priority": 1, "drill_name": "Ladder Drill", "instructions": "..."}]
}
```

**Confidence scale:**
- 1: 1-2 rounds (asks follow-up)
- 2: 3-5 rounds (early trends)
- 3: 5+ rounds, no shots (scorecard patterns)
- 4: With shot data (specific patterns)
- 5: Rich shot + trend data

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

**`conversations`**
- `id` BIGSERIAL PK
- `user_id` text
- `title` text
- `summary` text (optional, LLM-generated summary of older messages)
- `summarized_message_count` int (how many messages have been summarized)
- `created_at` timestamp

**`messages`**
- `id` BIGSERIAL PK
- `conversation_id` BIGINT FK
- `role` text (user/assistant)
- `content` text
- `created_at` timestamp

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

*Owner: Whoever touches backend. Update this first, then code.*
