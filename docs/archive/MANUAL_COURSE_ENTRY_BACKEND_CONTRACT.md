# Manual Course Entry — Backend Contract (Frontend's Ask)

> **From:** Claude Code (frontend)
> **To:** Kanary (backend / contract owner)
> **Status:** Proposal — needs Kanary to implement + fold into `API_CONTRACT.md`
> **Date:** 2026-08-05
> **Related:** `MANUAL_COURSE_ENTRY_SPEC.md` (approved by Duk)

---

## Why this doc exists

The feature spec and `TASK_BOARD.md` disagree on the backend shape:

- **Spec** (`MANUAL_COURSE_ENTRY_SPEC.md`): add a `manual_course` field to the
  existing `POST /api/v1/rounds`.
- **Task board / roadmap**: add a **new** `POST /api/v1/courses/manual` endpoint
  and store manual courses in a table.

I verified the **live** backend (`https://dimple-api.chokepointmonitor.com/openapi.json`)
on 2026-08-05: **neither exists yet.** `RoundPayload` has no `manual_course` field,
and there is no `/courses/manual` route. So the frontend can't be built against a
real contract until this is pinned + shipped.

## Recommendation: embed `manual_course` in `POST /api/v1/rounds` (no new endpoint)

This is the frontend's preferred shape, and it matches the spec's own decisions:

- The spec explicitly says manual courses are **not a course database**, are
  **immutable after round creation**, and are **not reused/searchable** later
  (Open Questions #2, #3). A `POST /courses/manual` endpoint + `manual_courses`
  table implies a reusable catalog we've already decided we don't want.
- One request instead of two (create-course → submit-round) — less latency, no
  orphaned-course state if the second call fails.
- Coach needs only round stats (score/putts/fairway/GIR), which come from
  `hole_data`. No course entity is required for coaching.

If Kanary has a strong backend reason to prefer the separate endpoint, that's a
contract call Kanary owns — just tell me the final shape and I'll build to it.

---

## Exact request the frontend will send

Extends the current `RoundPayload`. When `manual_course` is present, `course_id`
and `tee_box` are **omitted** (there is no API course and no tee data).

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-08-05",
  "course": { "name": "Creek Course", "city": "Lubbock", "state": "TX" },
  "manual_course": {
    "holes": 18,
    "par_values": [4,4,3,4,5,4,4,3,4, 4,4,3,4,5,4,4,3,4]
  },
  "handicap_index": 13.2,
  "hole_data": [
    { "hole_number": 1, "par": 4, "score": 5, "putts": 2, "fairway": false, "gir": false }
  ],
  "total_score": 94,
  "total_putts": 36
}
```

### Field rules the frontend guarantees
- `manual_course.holes` ∈ {9, 18}.
- `manual_course.par_values.count == holes`; each value ∈ {3, 4, 5}.
- `hole_data[*].yardage` omitted (no yardage in manual mode).
- `shots` **never** sent with `manual_course` (shot-by-shot disabled — no distances).
- `course.name` required; `city`/`state` may be empty strings.

### What the frontend needs the backend to do
1. Accept the request when `manual_course` is present **without** `course_id`/`tee_box`.
2. Compute `round_stats` from `hole_data` as usual:
   - `strokes_over_under = total_score − sum(par_values)`
   - `sg_putting`, `sg_approach`, `gir_percentage`, `fairway_percentage` as today.
   - `sg_driving` / `sg_short_game` omitted (need distances) — same as any
     scorecard-only round.
3. Persist `manual_course` (e.g. JSONB column on `rounds`) so History can render it.
4. Return the **same `RoundIngestResponse` shape** as a normal round (no FE decode change).

### Validation errors the frontend will surface
- `422` if both `manual_course` and `course_id` are provided.
- `422` if `par_values` count ≠ `holes`, or any par ∉ {3,4,5}.
- `422` if `shots` provided alongside `manual_course`.

---

## Does `GET /api/v1/rounds` need to change?

Round History must render manual courses. It already reads `course` (name/city/state),
so **no strict change is required** to display them. Optional-but-nice: include
`manual_course` (or a boolean flag) in the history row so the UI can badge a round
as manually entered. Not a blocker — tell me if it's cheap to add.

---

## Once Kanary confirms the shape, the frontend work is (already scoped in the spec)
- `ManualCourse.swift` model + `manual_course` field on `RoundPayload`.
- `ManualCourseEntryView` + view model (name/city/state, 9/18, par editor).
- "Enter manually" affordance on `CourseSearchView` (empty-results state).
- `ScorecardEntryView` conditional layout: no yardage, no shot-by-shot.
- `RoundService.submit(...)` carries `manual_course`.
- Update `API_CONTRACT.md` (Kanary owns the final word).

**Blocking on:** Kanary picking the shape above (or an alternative) and shipping it
to the live backend. I'll build + test the frontend end-to-end the moment it lands.
