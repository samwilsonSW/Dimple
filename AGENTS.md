# AGENTS.md

Conventions for any agent working on Dimple, regardless of harness
(opencode, Codex, Claude Code, OpenClaw, or anything driving a model through
OpenRouter). This file holds **invariants only** — nothing dated, nothing that
changes when a feature ships. If something here is wrong, fix it here.

Current state lives in `docs/STATUS.md`. Do not duplicate it into this file.

---

## What Dimple is

FastAPI + Supabase backend serving a golf round tracker and an LLM coach.
Two clients: a SwiftUI iOS app (`frontend/`) and an Expo/React Native app
(`mobile/`). Both talk to the same API.

---

## Read order

1. **This file** — conventions and landmines.
2. **`docs/API_CONTRACT.md`** — the seam. Endpoint behavior, rules, known risks.
3. **`docs/openapi.json`** — generated request/response shapes. Authoritative.
4. **`docs/STATUS.md`** — what's working right now, what's in flight.
5. **`docs/TASK_BOARD.md`** — only if you're picking up work rather than given it.

`docs/archive/` is finished specs kept for reference. Do not build from it
without checking it against the contract first — some of it is superseded.

---

## The One Rule

**`docs/API_CONTRACT.md` is the score.** If you change backend behavior, update
the contract in the same commit. If the contract and the code disagree, the
contract wins — that's a bug, file it rather than quietly matching the code.

Exception: request/response *shapes* are generated, not hand-written. See below.

---

## Shapes are generated, prose is written

Field-level schemas live in `docs/openapi.json`, emitted from the Pydantic
models. Never hand-edit that file and never transcribe shapes into markdown —
they drift, and drifted shapes are worse than none.

After changing any model or route:

```bash
cd backend && uv run python scripts/export_openapi.py
```

Commit the regenerated `docs/openapi.json` alongside your change. The smoke
test fails if it is stale.

`API_CONTRACT.md` carries what the schema cannot: semantics, error meanings,
and the risks table.

---

## Setup

The backend uses [uv](https://docs.astral.sh/uv/). Install it once
(`brew install uv`), then **never think about environments again** — `uv run`
creates and syncs `.venv` from `uv.lock` automatically before every command.

```bash
cd backend && uv run python scripts/smoke_test.py    # that's the whole setup
```

Do not `pip install` into your own Python, and do not activate anything. A bare
`python scripts/...` silently uses the wrong interpreter and *appears* to work —
always prefix with `uv run`.

`uv.lock` pins all 107 packages. That is deliberate: `docs/openapi.json` is
emitted by pydantic, so its version has to be fixed or the freshness check
reports drift that isn't real. If you change a dependency, run `uv lock` and
`uv export --format requirements-txt --no-hashes --no-dev -o requirements.txt`,
then commit both alongside `uv.lock`.

**Python version:** 3.12 only. `pydantic-core` fails to build on 3.14 (PyO3 max
3.13). If `uv` picks up system Python 3.14, fix with:
```bash
uv python install 3.12 && uv venv --python 3.12 && uv sync
```

## Verify before you hand back

```bash
cd backend && uv run python scripts/smoke_test.py                  # free, no credentials
cd backend && uv run python scripts/smoke_test.py --live           # needs a running server
cd backend && uv run python scripts/smoke_test.py --live --write   # also writes a round
cd backend && uv run python scripts/smoke_test.py --live --coach   # also spends LLM money
```

Default tier needs no credentials, no server, and no network — it checks that
the committed OpenAPI matches the code and that model invariants hold. **Run it
before reporting any backend work complete.** If you cannot run it, say so
explicitly rather than implying the work is verified.

There is no pytest suite. `backend/tests/` is a folder of manual scripts that
hit a live server and make paid LLM calls — they are not a regression gate and
running them proves little.

---

## Rules you will forget

| Rule | Why it bites |
|------|--------------|
| `user_id` UUIDs are **lowercase** | the `match_shots` RPC is case-sensitive and fails silently on uppercase |
| Dates are `YYYY-MM-DD` | no time component, anywhere |
| Putting distances are **feet**; everything else is **yards** | `before_distance_yards` means feet on a putt |
| `handicap_index` is a float `0.0–54.0` | not an int, not a string |
| Coach responses are slow (measured ~95s) | any added DB query or LLM call is a **taste decision**, not an implementation detail |

---

## Branching

- **`main`** is the release branch. Never push to it. Sam merges.
- **`Kanary`** is the integration branch. Work lands here.
- **Branch off `Kanary`. Never branch off another feature branch.**

That last rule is not style. In August 2026 five branches were each cut from
the previous branch instead of from `Kanary`, producing a stack that looked
like severe divergence and had to be collapsed by hand. Tag
`stable/kanary-pre-collapse` marks the state before that cleanup.

Before starting: `git checkout Kanary && git pull && git checkout -b <name>`.

---

## Authority

Authority is bound to **artifacts, not identities** — any agent may work any
part of this repo, so the rules attach to what you touch:

- Touch the backend → update `API_CONTRACT.md` and regenerate `openapi.json`.
- Touch the seam → run the smoke test before handing back.
- Touch a migration → say so loudly. Schema changes are the least reversible
  thing here, and `backend/migrations/` is applied by hand in the Supabase SQL
  editor. Never assume a migration has been run.

Read anything. Bugs here live in the seams — frontend payload, backend model,
and UUID casing have all been the root cause of the same failure.

---

## What to escalate rather than decide

Sam is the taste layer. Escalate rather than choosing silently:

- **Latency and model choice.** The coach is already slow enough to be a UX
  problem. Anything that adds round-trips is his call.
- **The coach's voice and tone.**
- **Anything that changes what the user sees or feels**, however small the diff.

Do not escalate things a machine can answer — whether it compiles, whether it
matches the contract, whether the smoke test passes. Answer those yourself.

---

## Frontend (SwiftUI)

SwiftUI views live in `frontend/dimple-frontend/`. Key files:
- `NewRoundView.swift` — round creation flow
- `CourseSearchView.swift` — course search + selection
- `ScorecardView.swift` — per-hole scorecard entry
- `RoundHistoryView.swift` — round list + stats
- `CoachChatView.swift` — coach conversation
- `Services/` — `CourseService.swift`, `RoundService.swift`, `CoachService.swift`

Patterns:
- Services are async/await, throw on error
- Views use `@State` + `Task` for async loads
- Backend URL: `https://dimple-api.chokepointmonitor.com` (production) or `http://localhost:8000` (dev)
- Auth: Supabase JWT passed in `Authorization` header

Testing:
- Simulator: `Cmd-R` in Xcode, select iPhone target
- Device: requires paid Apple Developer account + TestFlight (~15-30 min loop)
- Expo Go is ~30s for coach lab, but Swift is the v1.0.0 product

## Product principle

Make scorecard mode so good that players *want* to upgrade to shot-by-shot
because they see the value, not because it's forced. Low friction first, rich
data as a reward. When a change adds required input, weigh it against this.
