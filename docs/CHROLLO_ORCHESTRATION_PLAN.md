# Chrollo Orchestration Plan

## The Vision

**Duk is Chrollo. Kanary is the translator. Claude Code plays the instruments.**

Duk doesn't write code. He raises his hands — vision, taste, "ship or iterate" decisions. Kanary translates that into action. Claude Code builds the frontend. The system breathes.

---

## Role Definitions

| Role | Who | What They Do |
|------|-----|--------------|
| **Conductor** | Duk (Sam) | Vision, taste, product decisions, user experience feedback |
| **Translator** | Kanary (OpenClaw) | Turn Duk's intent into specs, coordinate backend + frontend, track state, document decisions |
| **Frontend Musician** | Claude Code | SwiftUI, Xcode, UI iteration, on-device testing |
| **Backend Musician** | Kanary (also) | FastAPI, Supabase, data pipeline, API design |

---

## How We Work Together

### Duk → Kanary
- "I want course search in the app"
- "The scorecard feels clunky"
- "Can we add a voice memo button?"

### Kanary → Action
- Write backend endpoint
- Update API contract
- Document what Claude Code needs to build
- Track in task board

### Kanary → Claude Code
- "Build SwiftUI view for course search per API_CONTRACT.md"
- "Endpoint is GET /api/v1/courses/search?q={name}"
- "Here's the response shape..."

### Claude Code → Duk
- Working build on device
- "Try this — tap course search, type 'Pinehurst'"

### Duk → Feedback
- "Feels good but the tee selector is buried"
- "Ship it" / "Iterate"

---

## Current State (Dimple)

| Feature | Backend | Frontend | Status |
|---------|---------|----------|--------|
| Course Search | ✅ | 🔄 | API live, needs SwiftUI |
| Scorecard Entry | ✅ Schema | ❌ | Not started |
| Voice Memo | ❌ | ❌ | Not started |
| Round History | ✅ | ❌ | Not started |
| AI Coach | ✅ | ✅ | Working |

---

## Communication Protocol

### Kanary ↔ Claude Code
- **API_CONTRACT.md** is the source of truth
- **Task board** tracks who's doing what
- **Git commits** on `Kanary` branch (backend) and `main` (frontend)

### When Duk Messages Kanary
1. Kanary checks task board
2. Updates or creates tasks
3. Executes backend work directly
4. Delegates frontend work to Claude Code with clear spec
5. Reports back to Duk

### When Claude Code Ships
1. Claude Code commits to `main`
2. Duk tests on device
3. Duk gives feedback to Kanary
4. Kanary coordinates next iteration

---

## Task Board Format

```markdown
## Active
- [ ] Course search UI (Claude Code) — blocked on: API ready ✅
- [ ] Scorecard entry view (Claude Code) — blocked on: design decision

## Done
- [x] Course search backend (Kanary)
- [x] AI Coach endpoint (Kanary)

## Blocked
- Voice memo parsing — waiting on: Duk to test flow
```

---

## Key Principle

**Duk never touches code. Kanary never touches Xcode. Claude Code never touches backend.**

The conductor doesn't play the violin. The translator doesn't write the symphony. Everyone plays their part.

---

## Files That Matter

| File | Purpose | Owner |
|------|---------|-------|
| `API_CONTRACT.md` | Backend ↔ Frontend interface | Kanary |
| `TASK_BOARD.md` | What's in progress | Kanary |
| `AGENT_REGISTRY.md` | Who does what | Kanary |
| `backend/` | FastAPI server | Kanary |
| `frontend/` | SwiftUI app | Claude Code |

---

*This is how we ship. Duk conducts. Kanary translates. Claude Code builds.*
