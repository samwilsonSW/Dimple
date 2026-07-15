# Dimple Task Board

> **Owner:** Kanary (OpenClaw)  
> **Updated:** 2026-07-14  
> **Rule:** Claude Code reads this file, picks up tasks marked `[CC]`, and reports completion to Duk. Kanary never assigns tasks to Duk directly — only surfaces blockers that need taste.

---

## Current State (2026-07-14)

**Core loop is functional:** Course search → Scorecard entry → Submit → Round History display.

**Next major feature:** Conversational Coach (Phase A + Phase B)

---

## Active

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

### Phase B: Frontend Coach Chat (Claude Code) — NOT STARTED

- [ ] **[CC] Replace coach endpoint** — switch from `/coach/ask` to `/coach/chat`
- [ ] **[CC] `CoachChatView`** — bubble-style chat interface
- [ ] **[CC] `ConversationListView`** — list of past conversations
- [ ] **[CC] Message threading** — send `conversation_id` for multi-turn
- [ ] **[CC] Entry points** — Round History "Ask Coach", Coach tab, post-submit
- [ ] **[CC] Loading/error states** — handle coach response latency
- [ ] **[CC] Accessibility** — VoiceOver for chat bubbles

**Blocked on:** Phase A backend completion
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

- **Submit idempotency** — Backlog. Add `client_round_id` + unique constraint to prevent duplicates on spotty networks.
- **Swipe-to-delete in Round History** — Needs backend `DELETE /rounds/{id}` endpoint first.
- **Voice memo parsing** — CANCELLED per Duk taste call.
- **Quick round mode** — CANCELLED per Duk taste call.
- **Enhanced scorecard fields** (miss direction) — Future enhancement for richer trend data.

---

## Merge Criteria (to main)

**Goal:** Conversational coach working end-to-end.

**Required:**
- [ ] Kanary: Phase A backend complete (new endpoints, migration applied)
- [ ] [CC] Phase B frontend complete (chat UI, conversation list)
- [ ] Duk: Test on device, confirm conversational flow feels right
- [ ] Duk: Merge Kanary → main

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
