# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-08-04  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Current State (2026-08-11)

**Target: v1.0.0** — Two features, then ship. Merge Kanary → main, tag release. Coach loading indicator **parked post-v1.0.0** per Duk.

**Core loop is functional:** Course search → Scorecard entry → Submit → Round History display → Coach chat.

---

## v1.0.0 Roadmap

| # | Feature | Status | Owner | Spec |
|---|---------|--------|-------|------|
| 1 | Manual Course Entry | Ready to build | Kanary backend ✅, [CC] frontend | `docs/MANUAL_COURSE_ENTRY_SPEC.md` |
| 2 | Coach Loading Indicator | **PARKED post-v1.0.0** | [CC] frontend | `docs/FRONTEND_LOADING_INDICATOR_SPEC.md` |
| 3 | Course Selection Flow Bug | Fix committed, needs verification | [CC] frontend | `docs/COURSE_SELECTION_FLOW_BUG_SPEC.md` |

---

## Active

### [CC] 1. Manual Course Entry — Frontend

**Status:** Ready for implementation. Backend is live.  
**Depends on:** ✅ Backend complete (Kanary shipped 2026-08-06)

**What to build:**
- [ ] `ManualCourse.swift` model + `manual_course` field on `RoundPayload`
- [ ] `ManualCourseEntryView` — form for name, city, state, hole count, par per hole
- [ ] `ManualCourseEntryViewModel` — validation, par calculation
- [ ] "Enter manually" button on `CourseSearchView` (when no results or always visible)
- [ ] Modify `ScorecardEntryView` for manual courses (no yardage, no shot mode)
- [ ] Wire to backend `POST /api/v1/rounds` with `manual_course` field

**Backend contract:**
- Send `manual_course: { holes: 9|18, par_values: [3,4,5,...] }` in `RoundPayload`
- Omit `course_id` and `tee_box`
- Omit `shots` (shot-by-shot disabled)
- Include `hole_data` as usual

**Spec:** `docs/MANUAL_COURSE_ENTRY_SPEC.md`

---

### Kanary 1. Manual Course Entry — Backend

**Status:** ✅ Complete (2026-08-06)  
**What was built:**
- [x] Migration 019 — `manual_course` JSONB column on `rounds`
- [x] `ManualCourse` model with validation (holes, par_values)
- [x] Updated `POST /api/v1/rounds` to accept `manual_course` field
- [x] Mutual exclusivity: `manual_course` ↔ `course_id` (422 if both)
- [x] Reject `shots` when `manual_course` present (422)
- [x] Updated `calculate_round_stats` to use `manual_par_values`
- [x] Updated `API_CONTRACT.md` v0.7.1
- [x] Deployed and verified live

**Backend verified:**
- ✅ Valid manual course payload → 200 + round_stats
- ✅ `manual_course` + `course_id` → 422
- ✅ `manual_course` + `shots` → 422
- ✅ `par_values` count ≠ `holes` → 422 (Pydantic validation)

---

### [CC] 2. Coach Loading Indicator — PARKED post-v1.0.0

**Status:** Parked per Duk (2026-08-11). Friendly error copy shipped. Visual indicator has rendering bug — not a blocker for v1.0.0.  
**What:** Visual feedback while coach is "thinking"

**Acceptance:**
- [x] Friendly error copy on failure (shipped)
- [ ] Optimistic message insertion (user message appears instantly)
- [ ] Animated "typing" indicator (pulsing dots or "Coach is thinking…")
- [ ] Retry UI on failure (not generic "Network connection was lost")
- [ ] State preserved on app background/foreground

**Files:** `CoachChatView.swift`, `CoachService.swift`, message models  
**Spec:** `docs/FRONTEND_LOADING_INDICATOR_SPEC.md`  
**Note:** Real fix is backend streaming/async. Queue for v1.1.

---

### [CC] 3. Course Selection Flow Bug Fix

**Status:** Spec drafted, ready for investigation + fix  
**Bug:** After selecting tees, user gets kicked back to course search. Must re-select course, then jumps to hole 1.

**Investigate:**
- [ ] Add logging to `NewRoundView` path changes
- [ ] Check for `presentationMode.dismiss()` in `CourseTeePickerView` / `RoundSetupView`
- [ ] Check if parent view recreation resets `NavigationStack`
- [ ] Confirm `RoundCourseSelection` Hashable conformance

**Fix:**
- [ ] Remove any explicit dismiss calls
- [ ] Stabilize `NavigationStack` identity if needed
- [ ] Defer `scorecardVM` assignment if it triggers recreation

**Files:** `NewRoundView.swift`, `CourseTeePickerView.swift`, `RoundSetupView.swift`, `ContentView.swift`  
**Spec:** `docs/COURSE_SELECTION_FLOW_BUG_SPEC.md`

---

## Recently Completed

- ✅ Coach reliability fixes (pooling, timeout, non-fatal verify) — merged to Kanary
- ✅ Auto-chat-titles — built, ready to merge
- ✅ Manual course entry spec — drafted, Duk approved

---

## Done (Last 30 Days)

- 2026-08-03: Coach reliability fixes merged to Kanary
- 2026-07-31: Auto-chat-titles feature built
- 2026-07-14: Phase B frontend built (chat UI, conversation list)
- 2026-07-14: Coach Rework Spec v2 — conversational, data-source-aware architecture
- 2026-06-29: PR #11 — fix round_id decode
- 2026-06-29: PR #10 — fix 500 on scorecard submit
- 2026-06-27: PR #9 — Round History List merged to Kanary
- 2026-06-25: PR #8 — Scorecard Entry View merged to Kanary
- 2026-06-24: Supabase key rotation complete
- 2026-06-22: Course Search UI merged to Kanary
- 2026-06-17: Course search backend built

---

## Blocked / Deferred (Post-v1.0.0)

- **Submit idempotency** — Backlog. Add `client_round_id` + unique constraint.
- **Swipe-to-delete in Round History** — Needs backend `DELETE /rounds/{id}`.
- **Voice memo parsing** — CANCELLED per Duk taste.
- **Quick round mode** — CANCELLED per Duk taste.
- **Enhanced scorecard fields** (miss direction) — Future enhancement.

---

## v1.0.0 Release Checklist

- [ ] Verify course selection bug fix (simulator + NAVLOG)
- [ ] Strip NAVLOG debug logging from `NewRoundView.swift`
- [ ] Build Manual Course Entry frontend
- [ ] Duk tests on device
- [ ] Screenshot + demo video for README
- [ ] Update README.md for v1.0.0
- [ ] Merge `feature/v1-frontend-fixes` → `Kanary`
- [ ] Merge `Kanary` → `main`
- [ ] Tag `v1.0.0`

## Post-v1.0.0 Backlog

- Coach loading indicator (streaming/async backend fix)
- Submit idempotency (`client_round_id` + unique constraint)
- Swipe-to-delete in Round History (needs `DELETE /rounds/{id}`)
- Enhanced scorecard fields (miss direction)

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

*Last updated: 2026-08-04 by Kanary*
