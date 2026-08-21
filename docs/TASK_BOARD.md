# Dimple Task Board

> **Pick a task. Build it. Mark it done.**

---

## Active

### 1. Course Selection Bug Fix
**Status:** Fix committed, needs verification  
**What:** After selecting tees, user gets kicked back to search. Should go to hole 1.  
**Where:** `NewRoundView.swift`, `CourseTeePickerView.swift`  
**Next:** Simulator test, confirm no path reset

---

## v1.0.0 Checklist

- [ ] Verify course selection bug fix
- [x] Build manual course entry frontend
- [ ] Test on device
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
