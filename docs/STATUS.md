# Dimple Status

> **Current state only** — what's working, what's in flight, what's blocked.
> Conventions and landmines live in [`AGENTS.md`](../AGENTS.md); interface
> semantics in [`API_CONTRACT.md`](API_CONTRACT.md). Keep those out of here so
> this file can change freely without anything else going stale.

---

## Right Now

**Version:** 1.0.0  
**Branch:** `Kanary` (working) → `main` (release)  
**API:** `https://dimple-api.chokepointmonitor.com`

### Working
- Course search + selection
- Scorecard entry (per-hole, auto-save)
- Round history with stats
- AI Coach chat (conversational, data-aware)
- Manual course entry (verified on device 22 Aug — full round entered end to end)

### In Progress
- Nothing. v1.0.0 is code-complete on `Kanary`; the release merge is the last step.
- Auto-chat-titles (built, ready to merge)

### Blocked / Deferred
- Coach loading indicator — parked post-v1.0.0
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
