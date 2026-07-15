# Wake Up Brief

> **Read this first. Every session. No exceptions.**
>
> This is the global state brief for all agents working on Dimple. It tells you what's happening, what's changed, and what matters right now.

---

## Current Status (Auto-Updated)

**Last Updated:** 2026-07-15
**API Version:** 0.7.0
**Branch:** Kanary (working branch — main is release, Kanary is where we build)
**Live API:** `https://dimple-api.chokepointmonitor.com` (named tunnel; stable)

### What's Working
- ✅ Course search backend + SwiftUI frontend (`/api/v1/courses/search`, `/api/v1/courses/{id}`)
- ✅ Scorecard Entry View — per-hole entry, draft auto-save, submit
- ✅ Round History List — scrollable cards with SG chips, pull-to-refresh
- ✅ Round ingestion (`POST /api/v1/rounds`) — full shot-by-shot + simple scorecard
- ✅ Round stats calculation — SG Putting, SG Approach, GIR%, Fairway%
- ✅ AI Coach (`POST /api/v1/coach/chat`) — conversational, data-source-aware, trend-based coaching
- ✅ Vector search (local embeddings + Supabase pgvector)

### What's In Progress
- ✅ Phase A: Backend coach rework — COMPLETE (tested, working; messages 502 fixed `ff423aa`)
- 🧪 Phase B: Frontend chat UI — BUILT, build green, all 3 endpoints verified live. In Duk simulator taste test → merge to Kanary on approval.

### What's Blocked / Deferred
- Conversational coach — Phase A complete (Kanary), Phase B built & in simulator test (Claude Code)
- Submit idempotency — backlog (duplicate prevention on retry)
- Swipe-to-delete in Round History — needs backend `DELETE /rounds/{id}`
- Voice memo parsing — CANCELLED per Duk taste
- Quick round mode — CANCELLED per Duk taste

---

## Files That Matter

| File | Why You Care |
|------|-------------|
| `docs/API_CONTRACT.md` | The score. Endpoint shapes, schemas, global rules. **Read before building.** |
| `docs/TASK_BOARD.md` | Who's doing what. Pick up `[CC]` tasks if you're Claude Code. |
| `docs/CHROLLO_ORCHESTRATION_PLAN.md` | How we work together. Authority, communication protocol, interrupt thresholds. |
| `docs/AGENT_STATUS.md` | **Claude Code's heartbeat.** Update as you work. Kanary reads this to track your state. |
| `README.md` | Project overview, stack, setup instructions. |

---

## Rules You Will Forget

1. **UUIDs are lowercase** - `550e8400...` not `550E8400...`. Case-sensitive `match_shots` will fail.
2. **Dates are `YYYY-MM-DD`** - no time component.
3. **Putting distances are in feet** - everything else is yards.
4. **Kanary owns the contract** - if backend changes, contract updates first.
5. **No pushing to main** - Kanary branch only. Duk merges.

---

## How to Use This

**If you're Kanary (OpenClaw):**
- Read this, then API_CONTRACT.md, then TASK_BOARD.md, then AGENT_STATUS.md
- Update this file when status changes
- Add `[CC]` tasks to TASK_BOARD.md for Claude Code

**If you're Claude Code:**
- Read this, then API_CONTRACT.md, then TASK_BOARD.md
- Pick up `[CC]` tasks
- Build against the contract - shapes are pinned there
- **Update `AGENT_STATUS.md` as you work** - progress, blockers, questions for Duk
- Report completion to Duk

**If you're Duk:**
- Read this to see current state at a glance
- Check TASK_BOARD.md for what's queued
- Give taste feedback, make ship/iterate calls
- Never touch code - conduct, don't play

---

## Changelog (Last 30 Days)

| Date | What Changed |
|------|-------------|
| 2026-07-14 | Phase B frontend built (chat UI, conversation list, entry points). Build green; endpoints verified live. Backend messages 502 (`asc=` kwarg) fixed + restarted. In Duk simulator test. |
| 2026-07-14 | Coach Rework Spec v2 — conversational, data-source-aware architecture. Phase A backend complete. |
| 2026-07-08 | Docs refreshed. Core loop complete. Ready for production test. |
| 2026-06-29 | PR #11 — round_id decode fix (String? → Int?). Migration 015 applied. |
| 2026-06-29 | PR #10 — fix 500 on scorecard submit (shots=None guard). |
| 2026-06-27 | PR #9 — Round History List merged to Kanary. |
| 2026-06-25 | PR #8 — Scorecard Entry View merged to Kanary. |
| 2026-06-24 | Supabase key rotation complete (legacy keys disabled). |
| 2026-06-22 | Course Search UI merged to Kanary. |
| 2026-06-17 | Course search backend built (GolfCourseAPI.com integration). |
| 2026-06-16 | API bumped to 0.6.0. Simple scorecard mode added. |

---

*This is the wake up call. Everyone reads it. Everyone knows the state. Now build.*
