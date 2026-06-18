# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-06-18  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Active

### Backend (Kanary)
- [x] **Scorecard stats calculation** — `POST /api/v1/rounds` now auto-calculates SG Putting, SG Approach, GIR%, Fairway% from `hole_data`. Stores in `round_stats` table.
- [x] **Round History endpoint** — `GET /api/v1/rounds?user_id={uuid}` — returns rounds with embedded `round_stats`.
- [ ] **Coach prompt refinement** — Trend-based coaching using `round_stats` is implemented but needs testing. May need iteration on prompt quality.
- [ ] **Voice memo placeholder** — schema support for `voice_memo_url` in `rounds` table (future parsing).

### Frontend (Claude Code)
- [ ] **[CC] Course Search UI** — Build SwiftUI view per API_CONTRACT.md §Course Search. 
  - **Endpoint:** `GET /api/v1/courses/search?q={query}&limit=10`
  - **Flow:** Search bar → results list (course name, city, state) → tap to select → tee box picker (from `/api/v1/courses/{course_id}`) → pass `course_id` + selected tee to round creation
  - **Rules:** Lowercase UUIDs for `user_id`. Handle empty states and API errors gracefully.
  - **Test:** Search "Pinehurst", select No. 2, pick Blue tees, verify `course_id` flows to round payload.
- [ ] **[CC] Scorecard Entry View** — Per-hole input: score, putts, fairway (toggle), GIR (toggle). Par 3 holes hide fairway toggle. Submit as `POST /api/v1/rounds` with `hole_data` array.
  - **Endpoint:** `POST /api/v1/rounds` with `hole_data` array
  - **Response includes:** `round_stats` with SG Putting, SG Approach, GIR%, Fairway%
  - **Rules:** Each hole needs `hole_number`, `par`, `score`, `putts`, `fairway` (bool, null for par 3), `gir` (bool)
  - **Test:** Enter 18 holes, verify response shows `round_stats` with calculated values
- [ ] **[CC] Round History List** — Display past rounds with course name, date, total score, key stats.
  - **Endpoint:** `GET /api/v1/rounds?user_id={uuid}&limit=10`
  - **Display:** Course name, date, total score, GIR%, Fairway%, Putts
  - **Test:** After entering rounds, verify list populates with stats from `round_stats`

---

## Done

- [x] API Contract v0.6.0
- [x] Course search backend
- [x] AI Coach endpoint
- [x] RAG retrieval with reflections

---

## Blocked

- Voice memo parsing — **CANCELLED per Duk taste call.** Simple scorecard + optional typed reflection is the path. Voice memos feel weird post-round.
- Quick round mode (just total score + reflection) — waiting on: Duk taste call

---

## How Claude Code Uses This

1. Read `API_CONTRACT.md` for endpoint shapes and rules
2. Pick up `[CC]` tasks from this board
3. Build in SwiftUI, test on device
4. When done, tell Duk: "Task X complete, ready for review"
5. Duk tests, gives taste feedback, or says "ship it"
6. If changes needed, Duk tells Kanary → Kanary updates task or files new one

---

*Last sync: Kanary → Duk → Claude Code workflow established.*
