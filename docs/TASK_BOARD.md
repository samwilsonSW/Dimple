# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-08-03  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Current State (2026-08-03)

**Core loop is functional:** Course search → Scorecard entry → Submit → Round History display → Coach chat.

**Recently completed:** Coach reliability fixes (pooling, timeout, non-fatal verify). Auto-chat-titles built.

**Next major feature:** Manual Course Entry (spec drafted, pending Duk review)

---

## Active

### Manual Course Entry (Spec Phase)

**Status:** Spec drafted in `feature/manual-course-entry`, pending Duk review  
**Problem:** GolfCourseAPI.com gaps block round entry (e.g., Creek Course at Meadowbrook GC)  
**Solution:** Lightweight fallback — user enters course name, city, state, holes, par values. Scorecard-only mode, full coach access.

**Next steps:**
- [ ] Duk reviews `docs/MANUAL_COURSE_ENTRY_SPEC.md`
- [ ] Kanary: Update API_CONTRACT.md with manual_course field
- [ ] Kanary: Write migration 019 (manual_course JSONB column)
- [ ] Kanary: Modify POST /api/v1/rounds to accept manual_course
- [ ] [CC] Build ManualCourseEntryView (form + par editor)
- [ ] [CC] Modify CourseSearchView to show "Enter manually" fallback
- [ ] [CC] Modify ScorecardEntryView for manual courses (no yardage, no shot mode)

---

### Phase A: Backend Coach Rework (Kanary) ✅ COMPLETE

- [x] **Data inventory builder** — count queries for round_stats, shot_embeddings, reflections
- [x] **Conditional prompt assembly** — only include sections when data exists
- [x] **Remove 25+ HCP gate** — replace with confidence scaling based on data richness
- [x] **Wire `get_trend_summary()`** — use scorecard trends when no shot data
- [x] **Skip RAG when no shots** — save compute and latency
- [x] **New `POST /api/v1/coach/chat` endpoint** — replaces `/api/v1/coach/ask`
- [x] **Conversation persistence** — `conversations` and `messages` tables
- [x] **New GET endpoints** — `/conversations`, `/conversations/{id}/messages`
- [x] **Update API contract** — v0.7.0
- [x] **Migration 017** — create conversations + messages tables

**Known Issues:**
- Confidence score: LLM overrides data-richness calculation. Under observation per Duk's preference.
- Tone: Direct/honest (not sugar-coated). Duk approves current intensity.

**Spec:** `docs/COACH_REWORK_SPEC.md`

### Phase B: Frontend Coach Chat (Claude Code) ✅ COMPLETE — merged to Kanary

- [x] **[CC] Replace coach endpoint** — switched `/coach/ask` → `/coach/chat` (old `ask()` removed)
- [x] **[CC] `CoachChatView`** — bubble-style chat (confidence bar, key-insights, expandable drill cards, typing indicator, scroll-to-bottom, inline error + Retry)
- [x] **[CC] `ConversationListView`** — Coach tab root; past conversations + New Chat
- [x] **[CC] Message threading** — sends `conversation_id` for multi-turn
- [x] **[CC] Entry points** — Coach tab, Round detail "Ask Coach", post-submit summary (both thread `round_id`)
- [x] **[CC] Loading/error states** — send + history load both covered
- [x] **[CC] Accessibility** — VoiceOver labels on all bubbles, drills, conversation cards

**Status:** `xcodebuild` green (generic iOS Simulator). All 3 endpoints verified live 200 against the new tunnel. Awaiting Duk simulator taste test → merge to Kanary on approval.
**Verified/fixed during integration:** messages endpoint requires `user_id` (contract updated); backend 502 (`asc=` kwarg) root-caused → Kanary fixed (`ff423aa`) → restarted → re-verified 200.
**Note:** work is uncommitted in the working tree (Duk merges). Base URL swapped to `evidence-dialogue-chronicle-officers.trycloudflare.com`.
**Spec:** `docs/COACH_REWORK_SPEC.md` (Phase B section)

---

## Recently Fixed

- ✅ **500 on scorecard submit** (PR #10) — `payload.shots` was `None` for scorecard-only submits
- ✅ **round_id type mismatch** (PR #11) — frontend expected `String?`, backend sent `Int`
- ✅ **Blank stats** — migration 015 applied (`avg_putts_per_hole`, `avg_score_to_par` columns)

---

## Done (Last 30 Days)

- 2026-07-14: Coach Rework Spec v2 — conversational, data-source-aware architecture
- 2026-06-29: PR #11 — fix round_id decode (String? → Int?). Migration 015 applied.
- 2026-06-29: PR #10 — fix 500 on scorecard submit (shots=None guard).
- 2026-06-27: PR #9 — Round History List merged to Kanary.
- 2026-06-25: PR #8 — Scorecard Entry View merged to Kanary.
- 2026-06-24: Supabase key rotation complete (legacy keys disabled).
- 2026-06-22: Course Search UI merged to Kanary.
- 2026-06-17: Course search backend built (GolfCourseAPI.com integration).

---

## Blocked / Deferred

- **🐞 Coach chat unreliable on follow-up messages (backend / Kanary)** — Open, found 2026-07-14 in simulator test. Backend→Supabase intermittently times out on the `.single()` conversation-verify (`main.py:561`, runs on every message after the first) → either `500 {"detail":"...[Errno 60] Operation timed out"}` or (when >60s) an app-side cancel seen as tunnel `context canceled`. Fix directions: retry/backoff + connection reuse on Supabase calls, make verify non-fatal, confirm Supabase not throttled. Frontend already bumped `send()` timeout 60s→180s (handles the slow-success case; not the 500s). Full write-up in `AGENT_STATUS.md`.
- **Coach chat long-wait UX** — Deferred per Duk (2026-07-14). Optional friendlier "coach is taking longer than usual…" copy for long LLM waits. Streaming/async is the real long-term fix (Kanary).
- **Submit idempotency** — Backlog. Add `client_round_id` + unique constraint to prevent duplicates on spotty networks.
- **Swipe-to-delete in Round History** — Needs backend `DELETE /rounds/{id}` endpoint first.
- **Voice memo parsing** — CANCELLED per Duk taste call.
- **Quick round mode** — CANCELLED per Duk taste call.
- **Enhanced scorecard fields** (miss direction) — Future enhancement for richer trend data.

---

## Merge Criteria (to main)

**Goal:** Conversational coach working end-to-end.

**Required:**
- [x] Kanary: Phase A backend complete (new endpoints, migration applied, messages 502 fixed)
- [x] [CC] Phase B frontend complete (chat UI, conversation list) — build green, endpoints verified
- [ ] Duk: Test on simulator, confirm conversational flow feels right
- [ ] Duk: Merge Phase B → Kanary (then Kanary → main)

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

*Last updated: 2026-07-14 by Kanary*
