# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-06-29  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Current State (2026-06-29)

**Core loop is functional:** Course search → Scorecard entry → Submit → Round History display.

### Recently Fixed
- ✅ **500 on scorecard submit** (PR #10) — `payload.shots` was `None` for scorecard-only submits
- ✅ **round_id type mismatch** (PR #11) — frontend expected `String?`, backend sent `Int`
- ✅ **Blank stats** — migration 015 applied (`avg_putts_per_hole`, `avg_score_to_par` columns)

---

## Active

### Backend (Kanary)
- [x] **Scorecard stats calculation** — `POST /api/v1/rounds` auto-calculates SG Putting, SG Approach, GIR%, Fairway% from `hole_data`. Stores in `round_stats` table.
- [x] **Round History endpoint** — `GET /api/v1/rounds?user_id={uuid}` — returns rounds with embedded `round_stats`.
- [ ] **Coach prompt refinement** — Trend-based coaching using `round_stats` is implemented but needs testing. May need iteration on prompt quality.
- [ ] **Submit idempotency** — Backlog. Add `client_round_id` + unique constraint to prevent duplicates on spotty networks. Not urgent.

### Frontend (Claude Code) — All Complete, Awaiting Duk Taste Test

**1. [CC] Course Search UI** ✅ COMPLETE (merged 2026-06-22)
- Files: `CourseSearchView.swift`, `CourseService.swift`, `CourseModels.swift`

**2. [CC] Scorecard Entry View** ✅ COMPLETE (merged 2026-06-25, PR #8)
- Files: `ScorecardEntryView.swift`, `RoundModels.swift`, `RoundService.swift`, `DraftRoundStore.swift`
- **Duk taste test:** Pending (on-device, sun readability, one-handed steppers)

**3. [CC] Round History List** ✅ COMPLETE (merged 2026-06-27, PR #9)
- Files: `RoundHistoryView.swift`, `RoundHistoryModels.swift`, `RoundHistoryService.swift`
- **Duk taste test:** Pending

---

## Merge Criteria (to main)

**Goal:** Course search + tee selection + scorecard input + round history working end-to-end.

**Required:**
- [x] [CC] Course Search UI
- [x] [CC] Scorecard Entry View
- [x] [CC] Round History List
- [x] Kanary: Backend handles all frontend calls correctly
- [ ] Duk: Test on device, confirm flow feels right
- [ ] Duk: Merge Kanary → main

**Then:** Rewrite README.md to reflect working features.

---

## Done (Last 30 Days)

- 2026-06-29: PR #11 — fix round_id decode (String? → Int?)
- 2026-06-29: PR #10 — fix 500 on scorecard submit (shots=None guard)
- 2026-06-29: Migration 015 — add missing `avg_putts_per_hole`, `avg_score_to_par` columns
- 2026-06-27: PR #9 — Round History List merged to Kanary
- 2026-06-25: PR #8 — Scorecard Entry View merged to Kanary
- 2026-06-24: Supabase key rotation complete (legacy keys disabled)
- 2026-06-22: Course Search UI merged to Kanary
- 2026-06-17: Course search backend built (GolfCourseAPI.com integration)

---

## Blocked / Deferred

- **Submit idempotency** — Backlog. Prevents duplicate rounds on retry. Simple: add `client_round_id` UUID to payload + unique constraint.
- **Swipe-to-delete in Round History** — Needs backend `DELETE /rounds/{id}` endpoint first.
- **Voice memo parsing** — CANCELLED per Duk taste call.
- **Quick round mode** — CANCELLED per Duk taste call.

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

*Last updated: 2026-06-29 by Kanary*
