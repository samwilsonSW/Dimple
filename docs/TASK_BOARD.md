# Dimple Task Board

> **Pick a task. Build it. Mark it done.**

---

## Active

### 1. Course Selection Bug Fix (bug #3) — DONE
**Status:** Fixed and verified. Start Round lands on hole 1 on the first tap.  
**What:** Start Round had to be tapped twice. `a256d84` treated the symptom —
it swapped a path reset for a spinner, so instead of being kicked back to
search you got a spinner that never resolved. Same race underneath: the
scorecard VM was written to `@State` and the route pushed in one closure, so
the destination built before the write landed and SwiftUI never rebuilt it.  
**Where:** `NewRoundView.swift` — VM now lives in a `RoundFlow` reference box  
**Why it stayed broken:** the fix is deterministic — the VM now lives in one
long-lived object, so the destination reads it in the same transaction that
writes it. Nothing left to race.

---

## v1.0.0 Checklist

- [x] Verify course selection bug fix
- [x] Build manual course entry frontend
- [x] Test on device
- [ ] Merge `Kanary` → `main`, tag `v1.0.0`

---

## Done (Recent)

- [x] Manual course entry frontend (builds clean; simulator/device pass still owed)
- [x] Manual course entry backend
- [x] Coach reliability fixes
- [x] Auto-chat-titles
- [x] Round history list
- [x] Scorecard entry view
- [x] Course search UI + backend

---

## Backlog

- Coach loading indicator (needs backend streaming)
- Submit idempotency (`client_round_id` + unique constraint)
- Swipe-to-delete (needs `DELETE /rounds/{id}`)
- Enhanced scorecard fields (miss direction)

---

## Cancelled

- Voice memo parsing
- Quick round mode

---

*Update this when you start or finish something.*
