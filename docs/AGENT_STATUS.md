# Agent Status Board

> **Who updates this:** Claude Code (frontend agent)  
> **Who reads this:** Kanary (OpenClaw orchestrator), Duk (conductor)  
> **When to update:** After every meaningful progress step, blocker, or completion  
> **Rule:** If you're Claude Code and you haven't updated this in >2 hours of work, update it.

---

## Claude Code — Current Task

- **Task:** Round History List — **claimed, building now**
- **Started:** 2026-06-25
- **Status:** In Progress
- **Spec:** `docs/ROUND_HISTORY_SPEC.md`
- **Branch:** Kanary (working branch — main is release, Kanary is where we build)
- **Previous:** Scorecard Entry View — ✅ merged to Kanary (PR #8, 2026-06-25), awaiting Duk's on-device taste test

## Progress — Round History List

- [ ] `RoundHistoryView` — scrollable list of round cards
- [ ] `RoundHistoryService` — fetch from `GET /api/v1/rounds`
- [ ] `RoundHistoryItem` models — decode response with nested `round_stats`
- [ ] Round card UI — course name, date, score, vs par, GIR, SG chips
- [ ] Empty state — "No rounds yet" with "+ New Round" button
- [ ] Pull-to-refresh
- [ ] Loading skeleton
- [ ] Error state with retry
- [ ] Tap card → placeholder detail view
- [ ] Accessibility (VoiceOver, Dynamic Type)
- [ ] Dark mode support

## Previous — Scorecard Entry View (COMPLETE)

- [x] Handicap setup screen + `HandicapStore` (UserDefaults) + Settings access (Coach menu)
- [x] Round setup screen (mode select + handicap pre-fill) from tee picker
- [x] Models: `RoundMode`, `DraftRound`, `HoleEntry`, encodable `RoundPayload`, `RoundStats`
- [x] `ScorecardEntryView` — Front/Back 9 tabs, per-hole steppers, nav, live totals
- [x] Per-hole form (score/putts/fairway/GIR) + edge cases (par 3, ace, eagle, putts cap)
- [x] Draft auto-save / resume (`DraftRoundStore`)
- [x] Review screen + submit to `POST /api/v1/rounds`
- [x] `RoundSummaryView` — display `round_stats`
- [x] Build green (xcodebuild, generic iOS Simulator)
- [x] Duk taste refinements: focused single-hole layout, score at bottom, type-in handicap (no stepper), centered + evenly-spaced middle
- [ ] On-device taste test (Duk) — sun readability, one-handed steppers, full flow

**Notes for Duk/Kanary:** 
- Round History List spec is at `docs/ROUND_HISTORY_SPEC.md` — read before building
- Scorecard: swipe-between-holes deferred (tap-to-jump + Front/Back tabs + Prev/Next cover navigation); per-hole yardage comes from `/courses/{id}` (first tee set, not the selected tee); post-submit stays on summary screen until Round History List ships
- Duk should test scorecard on device while Claude Code builds Round History List in parallel

## Blockers

- **Round submit was 500 + stats blank — root-caused by Claude Code 2026-06-29. Needs a Kanary-owned DB migration.** (NOT the `round_id` type — `round_id` is the int `id`, and the stats insert is wrapped in try/except so it can't 500.)
  1. **500 — FIXED in PR #10 (backend, please review — Kanary's lane).** `POST /api/v1/rounds` ran `for shot in payload.shots`, but `payload.shots` is `None` for scorecard-only submits (`hole_data`, no `shots`) → `TypeError: 'NoneType' object is not iterable`. Guarded with `payload.shots or []` and skip embedding when there are no narratives. Verified: the iOS payload that 500'd now returns 200.
  2. **Stats blank — NEEDS DB MIGRATION (Kanary to write/own).** The live `round_stats` table is missing `avg_putts_per_hole` and `avg_score_to_par` (table predates migration 002). The stats INSERT fails with `PGRST204` and is swallowed by the try/except, so rounds save but show "Stats unavailable". Introspected the live table to confirm exactly those two columns are missing. Proposed SQL (also in PR #10 as `migration 015`, for reference — Kanary owns the real one):
     ```sql
     ALTER TABLE round_stats
         ADD COLUMN IF NOT EXISTS avg_putts_per_hole NUMERIC(4, 2),
         ADD COLUMN IF NOT EXISTS avg_score_to_par   NUMERIC(4, 2);
     NOTIFY pgrst, 'reload schema';
     ```
  - Cleanup: junk test rounds under fake UUID `550e8400…` ("ZZ Test Course", "Repro Course" ×2) from shape-verification — harmless, don't show for real users; delete whenever.

## Questions for Duk

- None

## Completed (Last 7 Days)

- 2026-06-25: **Claude Code — Scorecard Entry View merged to Kanary (PR #8).** Full per-hole entry flow + Duk's taste refinements (focused single-hole screen, score at bottom, type-in handicap, centered/even middle). `xcodebuild` green; on-device taste test pending.
- 2026-06-24: **Claude Code — Supabase key rotation complete (Path B).** Installed `supabase==2.30.0` into the local `.venv` (the upgrade Kanary pinned in requirements). Verified the backend connects with the new `sb_secret_…` key — `GET /api/v1/rounds` returns 200 (was 500 under 2.10.0). Verified the iOS side: `supabase-swift` has no JWT-format gate, and Supabase accepts the new `sb_publishable_…` key (401 permission-denied = valid key, RLS-locked). Duk disabled the legacy keys → the leaked anon key is revoked and the GitGuardian incident is resolved. Security thread fully closed.
- 2026-06-23: **Kanary (backend/orchestrator) — supabase-py upgrade** — Bumped `supabase==2.10.0` → `supabase==2.30.0` in `backend/requirements.txt`. Fixes 500 errors caused by v2.10.0's hard JWT regex rejecting new `sb_secret_…` anon keys. Committed and pushed to `main`.
- 2026-06-23: **Kanary (backend/orchestrator) — main branch catch-up** — `main` is now the single source of truth. All Kanary branch work merged. Docs updated (TASK_BOARD, WAKE_UP, CHROLLO_ORCHESTRATION_PLAN). AGENT_STATUS.md created for Claude Code heartbeat.
- 2026-06-23: Security fix — moved the Supabase anon key out of source into a git-ignored `Secrets.xcconfig` (build-time Info.plist injection, runtime read). Tripped GitGuardian on the public repo. Open as PR into Kanary (`security/externalize-supabase-key`). Anon key being rotated in Supabase; RLS verified (anon role has no table access).
- 2026-06-22: Course Search UI complete — search, select, tee picker working

---

## Session Decisions Log (2026-06-24 → 06-25)

**Security / keys**
- Supabase **anon key removed from source** → git-ignored `Secrets.xcconfig`, injected into the generated `Info.plist` via `$(SUPABASE_ANON_KEY)`, read at runtime. Project URL stays in source (not secret; `//` breaks xcconfig parsing).
- **Migrated to Supabase's new API keys**: `sb_publishable_…` (iOS) + `sb_secret_…` (backend). Required upgrading `supabase-py` 2.10 → 2.30 (old version's JWT regex rejected the non-JWT keys). Legacy keys **disabled** → leaked anon key revoked; **GitGuardian incident resolved**. RLS verified (anon role has no table access — the leaked key was inert even before rotation).

**Workflow**
- **Kanary = working branch, `main` = release; Duk merges.** Never push to `main` without explicit, per-instance permission. Features land via PRs into Kanary (PR #7 = security, PR #8 = scorecard).

**Scorecard feature (Duk taste calls)**
- **Hole screen = focused single-hole layout** (replaced the spec's scrolling scorecard list): top = hole + running totals, middle = fairway/GIR/putts (centered, evenly spaced), bottom = score +/- and a large pinned Next/Submit (thumb zone). The full all-holes scorecard lives behind the top-right "Scorecard" button (review screen).
- **Handicap = type-in only** (no 0.1 stepper); stored locally in `UserDefaults` (first-launch setup + Coach-menu settings); per-round override does not change the stored default.
- Round modes: Full 18 / Front 9 / Back 9 / Play Until Dark (flexible early submit). **Quick round mode cancelled** (Duk taste).
- Edge cases: hole-in-one → putts 0 / GIR yes / locked; eagle-or-better → auto-GIR; putts capped at score−1. Single active draft in `UserDefaults` with a resume prompt.

**Deferred / known limits**
- Swipe-between-holes deferred (tap-to-jump + Prev/Next + "Scorecard" jump view cover navigation).
- Per-hole yardage comes from `/courses/{id}` (backend derives it from the first tee set, not the selected tee).
- Post-submit stays on the summary screen until **Round History List** exists (next task).

---

## How Claude Code Uses This File

1. **Update as you go.** After every session or meaningful milestone, edit this file.
2. **Be specific.** "Building view" is bad. "Created ScorecardEntryView.swift with hole list" is good.
3. **Flag blockers immediately.** If you're stuck, write it here. Kanary will surface it to Duk.
4. **Ask questions here.** If you need a taste decision from Duk, put it in "Questions for Duk".
5. **Commit with the code.** This file lives in the repo. Update it, commit it, push it.

## How Kanary Uses This File

1. **Read during wake-up.** Check this file every session to see Claude Code's current state.
2. **Surface blockers.** If there's a blocker, ping Duk with context.
3. **Route questions.** If Claude Code has a question for Duk, relay it or answer if within my authority.
4. **Update TASK_BOARD.** Cross-reference this file when updating the task board.

## Format

```markdown
## Claude Code — Current Task
- **Task:** [Task name from TASK_BOARD.md]
- **Started:** [YYYY-MM-DD]
- **Status:** Not started / In Progress / Blocked / Complete
- **Branch:** [branch name]

## Progress
- [x] Done item
- [ ] Todo item

## Blockers
- [Description and context]

## Questions for Duk
- [Question that needs taste/priority decision]

## Completed (Last 7 Days)
- [YYYY-MM-DD]: [What was completed]
```

---

*Last updated: 2026-06-25 (Claude Code — scorecard merged + session decisions logged)*
*Next expected update: When Claude Code starts Scorecard Entry View*
