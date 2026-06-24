# Chrollo Orchestration Plan

> Refined 2026-06-17 after a live working session. The original framing
> (territorial walls, frontend→`main`/backend→`Kanary`) is superseded by the
> model below. The vision is unchanged; the mechanics are sharper.

## The Vision

**Duk is Chrollo. Kanary is the translator. Claude Code plays the instruments.**

Duk doesn't write code. He raises his hands — vision, taste, "ship or iterate" decisions. Kanary translates that into action and holds the connective tissue. Claude Code builds the surface Duk cares most about. The system breathes.

A conductor can conduct without playing a note only because three things are true: **everyone reads the same score, everyone can hear each other, and everyone shares a tempo.** Our job is to build machine-enforced versions of all three — a contract, verification, and coordination. The unglamorous scaffolding is *precisely what earns* the human the right to stop touching code.

---

## Role Definitions

| Role | Who | What They Do |
|------|-----|--------------|
| **Conductor** | Duk (Sam) | Vision, taste, product decisions, UX feedback, ship/iterate |
| **Translator / Planner** | Kanary (OpenClaw) | Turn intent into specs, own the API contract, plan large-scope problems and the web of connections, track state, and **ping Duk unprompted when something needs the conductor** |
| **Frontend Musician** | Claude Code | SwiftUI, Xcode, UI iteration, on-device testing |
| **Backend Musician** | Kanary (also) | FastAPI, Supabase, data pipeline, API design |

### Why Claude Code = frontend (it's not a wall)
The frontend is the **taste surface** — customer-facing, the thing that decides adoption and impression — and it's the surface Duk interfaces through in real time. So the place his attention is most valuable and the place he has hands are the same place. This is attention economics, not territory.

---

## Two Interaction Modes

The two instruments have different latencies, and that asymmetry is the point:

- **Claude Code — synchronous / hands-on.** The *rehearsal room*. Duk is present, the loop is tight, taste is applied directly.
- **Kanary — asynchronous / background.** The *section leader between rehearsals*. Sees the whole web of connections, plans big-scope work, and taps Duk on the shoulder when needed.

---

## Authority, Not Walls

**Knowledge is unbounded. Authority is bounded.**

- **Every agent can READ everything.** Debugging lives in the seams — the night the AI Coach broke, the root cause spanned frontend payload *and* backend model *and* UUID casing. A "never look at the other side" rule would have blocked the fix.
- **Rules govern who CHANGES what:** Claude Code commits frontend, Kanary commits backend.
- **Kanary owns the API contract (the seam).** Claude Code proposes frontend needs against it; each side implements its own half; anyone may diagnose across it.
- **Taste reaches into the backend too.** Latency, LLM model choice, and the coach's voice are taste-bearing. Kanary must surface UX-affecting backend choices to Duk as taste decisions — never decide them silently.

---

## The Interrupt Threshold (make-or-break)

Kanary's unprompted pings are what make Duk an orchestrator instead of a poller — and signal quality is everything. Too noisy → he mutes it; too quiet → things rot. Every event sorts into one tier:

- **Interrupt now** — needs taste or a priority call only Duk can make. ("Coach is fast but the tone feels clinical — ship or iterate?")
- **Digest** — FYI, batched. ("3 backend changes merged, all green.")
- **Never surface** — self-healed. (A flaky test retried and passed.)

---

## How We Work Together

### Duk → Kanary
- "I want course search in the app"
- "The scorecard feels clunky"
- "Can we add a voice memo button?"

### Kanary → Action
- Write backend endpoint, update the API contract, spec what Claude Code builds, track it.

### Kanary → Claude Code
- "Build SwiftUI view for course search per the contract. Endpoint, request, and response shape are pinned there."

### Claude Code → AGENT_STATUS.md
- Update as you work: progress, blockers, questions for Duk. Kanary reads this. No more "what's Claude Code doing?"

### Claude Code → Duk
- Working build on device. "Try this — tap course search, type 'Pinehurst'."

### Duk → Feedback
- "Feels good but the tee selector is buried." / "Ship it." / "Iterate."

---

## Communication Protocol

### Source of truth
- **API_CONTRACT.md** — the seam, owned by Kanary. Pins request/response shapes *and* the rules a human keeps forgetting (e.g. **UUIDs are lowercase**; case-sensitive `match_shots`).
- **TASK_BOARD.md** — what's in progress and who owns it.
- **AGENT_STATUS.md** — Claude Code's real-time heartbeat. Progress, blockers, questions. Kanary reads this to track frontend state without polling Duk.

### Branching
- **`Kanary` is the working branch** — both frontend and backend land here. `main` is the release branch; Duk merges when ready.
- **No two agents race the same branch.** Coordinate handoffs or work in isolated branches/worktrees that merge through a gate — divergence already bit us once.

### When Claude Code Ships
1. Change passes an automated gate (build, contract tests, simulator smoke test) — *then* it reaches Duk.
2. Duk is asked only what a machine can't answer: "feel right? ship or iterate?" — never "does it compile / match the API?"
3. Duk's feedback → Kanary coordinates the next iteration.

---

## Current State (Dimple)

| Feature | Backend | Frontend | Status |
|---------|---------|----------|--------|
| Course Search | ✅ | ✅ | Complete — search, select, tee picker working |
| Scorecard Entry | ✅ Schema | 🔄 | Next up — Claude Code building now |
| Voice Memo | ❌ | ❌ | Cancelled per Duk taste |
| Round History | ✅ | ❌ | Blocked on scorecard entry |
| AI Coach | ✅ | ✅ | Working (frontend now sends authenticated, lowercased `user_id`) |

**Open risks to track:** LLM thinking-mode latency vs the iOS ~60s request timeout; `match_shots` is case-sensitive on `user_id`.

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

## The Showcase Goal

Success isn't "agents wrote code." It's driving to ~zero the number of times Duk has to think **below his altitude** (ports, payload shapes, UUID casing, rebuild order — all of which cost him real time this session), while his inputs stay purely *taste and priority*.

The enablers, in leverage order:
1. **Executable API contract** — generate OpenAPI from FastAPI, codegen the Swift client. Make seam mismatches a compile error, not a runtime 422.
2. **Automated verification gate** — so the loop closes itself and only taste reaches Duk.
3. **Agent coordination** — no racing the branch.
4. **Durable decision log** — so decisions persist across sessions instead of evaporating in chat.

---

## Key Principle

**Authority is bounded; knowledge is not.** The conductor doesn't play the violin, but every musician can read the whole score. The Requiem isn't that the human left the pit — it's that the pit no longer needs him in it.

---

## Files That Matter

| File | Purpose | Owner |
|------|---------|-------|
| `API_CONTRACT.md` | Backend ↔ Frontend interface (incl. casing rules) | Kanary |
| `TASK_BOARD.md` | What's in progress | Kanary |
| `AGENT_STATUS.md` | Claude Code's real-time status — progress, blockers, questions | Claude Code (writes), Kanary (reads) |
| `AGENT_REGISTRY.md` | Who does what | Kanary |
| `backend/` | FastAPI server | Kanary |
| `frontend/` | SwiftUI app | Claude Code |

---

*This is how we ship. Duk conducts. Kanary translates. Claude Code builds. Everyone reads the score.*
