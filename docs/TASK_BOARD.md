# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-06-23  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Active

### Backend (Kanary)
- [x] **Scorecard stats calculation** — `POST /api/v1/rounds` now auto-calculates SG Putting, SG Approach, GIR%, Fairway% from `hole_data`. Stores in `round_stats` table.
- [x] **Round History endpoint** — `GET /api/v1/rounds?user_id={uuid}` — returns rounds with embedded `round_stats`.
- [ ] **Coach prompt refinement** — Trend-based coaching using `round_stats` is implemented but needs testing. May need iteration on prompt quality.
- [ ] **Voice memo placeholder** — schema support for `voice_memo_url` in `rounds` table (future parsing).

### Frontend (Claude Code) — Priority Order

**1. [CC] Course Search UI** ✅ COMPLETE
- **Endpoint:** `GET /api/v1/courses/search?q={query}&limit=10`
- **Flow:** Search bar → results list (course name, city, state) → tap to select → tee box picker (from `/api/v1/courses/{course_id}`) → pass `course_id` + selected tee to round creation
- **Rules:** Lowercase UUIDs for `user_id`. Handle empty states and API errors gracefully.
- **Test:** Search "Rawls", select "The Rawls Course At Texas Tech", pick Black/Red/White/Gold tees, verify `course_id` flows to round payload.
- **Status:** Merged to Kanary branch 2026-06-22. Files: `CourseSearchView.swift`, `CourseService.swift`, `CourseModels.swift`

**2. [CC] Scorecard Entry View** — ACTIVE
- **Endpoint:** `POST /api/v1/rounds` with `hole_data` array
- **Flow:** Receive course_id + tee selection → load hole_data template (par, yardage from course details) → per-hole input: score, putts, fairway (toggle, hidden on par 3), GIR (toggle) → submit → display round_stats response
- **Response includes:** `round_stats` with SG Putting, SG Approach, GIR%, Fairway%
- **Rules:** Each hole needs `hole_number`, `par`, `score`, `putts`, `fairway` (bool, null for par 3), `gir` (bool)
- **Test:** Enter 18 holes for Rawls Course, verify response shows `round_stats` with calculated values
- **Blocks:** Round History List (needs rounds to exist)

**3. [CC] Round History List**
- **Endpoint:** `GET /api/v1/rounds?user_id={uuid}&limit=10`
- **Flow:** Display past rounds with course name, date, total score, key stats → tap to view detail (future)
- **Display:** Course name, date, total score, GIR%, Fairway%, Putts
- **Test:** After entering rounds, verify list populates with stats from `round_stats`

---

## Merge Criteria (to main)

**Goal:** Course search + tee selection + scorecard input working end-to-end.

**Required:**
- [ ] [CC] Course Search UI — search, select, pick tee
- [ ] [CC] Scorecard Entry View — 18 holes, submit, get stats back
- [ ] [CC] Round History List — shows past rounds with stats
- [ ] Kanary: Verify backend handles all frontend calls correctly
- [ ] Duk: Test on device, confirm flow feels right

**Then:** Merge Kanary → main, rewrite README.md to reflect working features.

---

## Done

- [x] API Contract v0.6.0
- [x] Course search backend
- [x] AI Coach endpoint
- [x] RAG retrieval with reflections
- [x] Scorecard stats calculation (SG Putting, SG Approach, GIR%, Fairway%)
- [x] Round history endpoint

---

## Blocked

- Voice memo parsing — **CANCELLED per Duk taste call.** Simple scorecard + optional typed reflection is the path. Voice memos feel weird post-round.
- Quick round mode (just total score + reflection) — waiting on: Duk taste call

---

## How Claude Code Uses This

1. Read `API_CONTRACT.md` for endpoint shapes and rules
2. Pick up `[CC]` tasks from this board
3. **Update `AGENT_STATUS.md` as you work** — progress, blockers, questions. Kanary reads this.
4. Build in SwiftUI, test on device
5. When done, tell Duk: "Task X complete, ready for review"
6. Duk tests, gives taste feedback, or says "ship it"
7. If changes needed, Duk tells Kanary → Kanary updates task or files new one

---

*Last sync: Kanary → Duk → Claude Code workflow established.*
