# Dimple Status

> **Current state only** — what's working, what's in flight, what's blocked.
> Conventions and landmines live in [`AGENTS.md`](../AGENTS.md); interface
> semantics in [`API_CONTRACT.md`](API_CONTRACT.md). Keep those out of here so
> this file can change freely without anything else going stale.

---

## Right Now

**Version:** 1.2.0  
**Branch:** `Kanary` (working) → `main` (release)  
**API:** `https://dimple-api.chokepointmonitor.com`

### Working
- Course search + selection
- Scorecard entry (per-hole, auto-save, first-putt distance + penalty shots)
- Round history with stats
- AI Coach chat (conversational, data-aware, streaming)
- Manual course entry (verified on device 22 Aug — full round entered end to end)

### Just landed — needs a device check
- Coach streaming (`POST /coach/chat/stream`, SSE). This fixes the real cause of
  "couldn't reach the coach": the API sits behind Cloudflare, which gives the
  origin 100s to start responding, and a long reply blew through it and came
  back as a 524. Reproduced on 2026-08-29 — a 125s reply returned HTTP 524.
  Streaming sends the first byte before any database work, so the clock never
  starts. **Not yet verified against the live server or on device.**
- The coach LLM no longer emits JSON. It writes a line-tagged format
  (`backend/app/services/coach_format.py`). A malformed reply used to 502 and
  throw away the whole paid call; now a bad tag costs one drill card.

### In Progress
- Strokes-gained consistency rework — `feature/sg-consistency-rework`, needs
  review + merge. All four categories now attribute against the surface's own
  conditional expectations: conservation exact, no crash at any handicap,
  self-play ≈ 0, fabricated `broadie.py` data deleted, penalties documented
  honestly, CI gate added (`scripts/verify_sg.py`). Rounds are recomputable
  from `hole_scores` once merged — stored SG values predate the fix.
  See the "State of play" section of `docs/SG_REBUILD.md`.
- Still open after that merge: the level residual (surface under-counts putts;
  bracket-average rounds total −2…−9) — calibration data work, and the
  detailed shot-by-shot ingestion path still runs the retired hand-typed
  baselines. Both tracked in `docs/SG_REBUILD.md`.

### Needs doing by hand
- Migration 020 (`hole_scores`) is applied to the live project. Any other
  environment needs it run in the Supabase SQL editor before rounds will store
  per-hole data. Without it, ingestion still succeeds and logs a warning.

### Blocked / Deferred
- Coach loading indicator — unparked by streaming; the typing indicator now
  hands over to live text. Worth a design pass on device.
- Submit idempotency — backlog
- Swipe-to-delete — needs backend DELETE endpoint

---

## v1.0.0 Checklist

- [x] Verify course selection bug fix (bug #3 fixed in #19, verified in simulator)
- [x] Build manual course entry frontend
- [x] Test on device
- [x] Merge `Kanary` → `main`, tag v1.0.0

---

## The One Rule

**API_CONTRACT.md is the score.** If you change the backend, update the contract first. If the contract and code disagree, the contract wins — file a bug.

Everything else is negotiable.

---

*Last updated: 2026-08-22*

## This Week

- PR #18 merged — CI on every push/PR to Kanary (7/7 green)
- Swift v1.0.0 confirmed as ship target. Expo stays coach lab.
- Memory cleaned up — old notes archived, MEMORY.md rewritten to current reality
- Server fixed — Python 3.12 (was 3.14, broke pydantic-core)
