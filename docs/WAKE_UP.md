# Wake Up Brief

> **Read this first. Every session. No exceptions.**
> 
> This is the global state brief for all agents working on Dimple. It tells you what's happening, what's changed, and what matters right now.

---

## Current Status (Auto-Updated)

**Last Updated:** 2026-06-23  
**API Version:** 0.6.0  
**Branch:** Kanary (integration branch for both frontend and backend)

### What's Working
- ✅ Course search backend (`/api/v1/courses/search`, `/api/v1/courses/{id}`)
- ✅ Round ingestion (`POST /api/v1/rounds`) — full shot-by-shot + simple scorecard
- ✅ AI Coach (`POST /api/v1/coach/ask`) — RAG with reflections, SG aggregation
- ✅ Vector search (local embeddings + Supabase pgvector)

### What's In Progress
- 🔄 Scorecard Entry View (Claude Code) — next priority
- 🔄 Round History List (Claude Code) — blocked on scorecard
- 🔄 Scorecard aggregation backend refinement (Kanary)

### What's Blocked
- Voice memo flow — waiting on Duk taste decision
- Quick round mode — waiting on Duk taste decision

---

## Files That Matter

| File | Why You Care |
|------|-------------|
| `docs/API_CONTRACT.md` | The score. Endpoint shapes, schemas, global rules. **Read before building.** |
| `docs/TASK_BOARD.md` | Who's doing what. Pick up `[CC]` tasks if you're Claude Code. |
| `docs/CHROLLO_ORCHESTRATION_PLAN.md` | How we work together. Authority, communication protocol, interrupt thresholds. |
| `README.md` | Project overview, stack, setup instructions. |

---

## Rules You Will Forget

1. **UUIDs are lowercase** — `550e8400...` not `550E8400...`. Case-sensitive `match_shots` will fail.
2. **Dates are `YYYY-MM-DD`** — no time component.
3. **Putting distances are in feet** — everything else is yards.
4. **Kanary owns the contract** — if backend changes, contract updates first.
5. **No pushing to main** — Kanary branch only. Duk merges.

---

## How to Use This

**If you're Kanary (OpenClaw):**
- Read this, then API_CONTRACT.md, then TASK_BOARD.md
- Update this file when status changes
- Add `[CC]` tasks to TASK_BOARD.md for Claude Code

**If you're Claude Code:**
- Read this, then API_CONTRACT.md, then TASK_BOARD.md
- Pick up `[CC]` tasks
- Build against the contract — shapes are pinned there
- Report completion to Duk

**If you're Duk:**
- Read this to see current state at a glance
- Check TASK_BOARD.md for what's queued
- Give taste feedback, make ship/iterate calls
- Never touch code — conduct, don't play

---

## Changelog (Last 7 Days)

| Date | What Changed |
|------|-------------|
| 2026-06-18 | API_CONTRACT.md + TASK_BOARD.md created. Orchestration workflow established. |
| 2026-06-16 | Course search backend added. Simple scorecard mode added. API bumped to 0.6.0. |
| 2026-05-22 | Reflections, SG aggregation, score variance added. API 0.5.0. |

---

*This is the wake up call. Everyone reads it. Everyone knows the state. Now build.*
