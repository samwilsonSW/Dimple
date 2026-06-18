# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-06-18  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Active

### Backend (Kanary)
- [ ] **Scorecard API** — `POST /api/v1/rounds` already accepts `hole_data`, but no aggregation logic yet. Need to calculate totals, GIR%, fairway% from simple scorecard.
- [ ] **Round History endpoint** — `GET /api/v1/rounds?user_id={uuid}` — list all rounds for a player with summary stats.
- [ ] **Voice memo placeholder** — schema support for `voice_memo_url` in `rounds` table (future parsing).

### Frontend (Claude Code)
- [ ] **[CC] Course Search UI** — Build SwiftUI view per API_CONTRACT.md §Course Search. Endpoint: `GET /api/v1/courses/search?q={query}&limit=10`. Display results list, tee selector. On select, pass `course_id` to round creation.
- [ ] **[CC] Scorecard Entry View** — Per-hole input: score, putts, fairway (toggle), GIR (toggle). Par 3 holes hide fairway toggle. Submit as `POST /api/v1/rounds` with `hole_data` array.
- [ ] **[CC] Round History List** — Display past rounds with course name, date, total score. Tap to view detail (future).

---

## Done

- [x] API Contract v0.6.0
- [x] Course search backend
- [x] AI Coach endpoint
- [x] RAG retrieval with reflections

---

## Blocked

- Voice memo parsing — waiting on: Duk to test flow (do we record in-app or attach existing?)
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
