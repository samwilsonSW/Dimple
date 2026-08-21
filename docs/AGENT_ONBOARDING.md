# Agent Onboarding — Dimple

> Quick-start for any agent (OpenCode, Claude Code, Codex, OpenClaw) picking up Dimple work.
> Read this first, then `AGENTS.md`, then `API_CONTRACT.md`.

---

## What You're Working On

Golf intelligence app. FastAPI backend + SwiftUI iOS frontend. Expo app exists for coach lab only — **Swift is the v1.0.0 product**.

Repo: `samwilsonSW/Dimple`
- `main` — release (Sam merges only)
- `Kanary` — integration branch (work lands here)
- **Branch off `Kanary`. Never off another feature branch.**

---

## First Steps

```bash
cd ~/Desktop/Dimple
git checkout Kanary && git pull
git checkout -b feature/your-thing
```

Backend setup (one command):
```bash
cd backend && uv run python scripts/smoke_test.py
```

If that passes, you're ready. If it fails, check Python version — must be 3.12, not 3.14.

---

## Where Things Live

| Thing | Path |
|-------|------|
| Backend | `backend/` |
| SwiftUI frontend | `frontend/dimple-frontend/` |
| Expo coach lab | `mobile/` (not shipping) |
| API contract | `docs/API_CONTRACT.md` |
| Generated schemas | `docs/openapi.json` |
| Current status | `docs/STATUS.md` |
| Task board | `docs/TASK_BOARD.md` |
| Migrations | `backend/migrations/` |

---

## Running the Backend

The server runs in tmux:
```bash
tmux attach -t dimple-server    # see logs
# Ctrl-B D to detach
```

Port: `8000`
Tunnel: `https://dimple-api.chokepointmonitor.com`

Restart if needed:
```bash
tmux kill-session -t dimple-server
cd ~/Desktop/Dimple/backend && tmux new-session -d -s dimple-server "uv run python run.py"
```

**Never `pip install`.** Use `uv run` for everything. `uv.lock` pins all packages.

---

## Verify Before Handing Back

```bash
cd backend && uv run python scripts/smoke_test.py          # free, no server
cd backend && uv run python scripts/smoke_test.py --live   # needs server running
```

Run the free tier before claiming work is done. If you can't run it, say so explicitly.

---

## Backend Changes — The One Rule

**`API_CONTRACT.md` is the score.** Update it in the same commit as your code change. Then regenerate OpenAPI:

```bash
cd backend && uv run python scripts/export_openapi.py
```

Commit both together. The smoke test fails if `openapi.json` is stale.

---

## Rules That Bite

| Rule | Why |
|------|-----|
| `user_id` UUIDs **lowercase** | `match_shots` RPC is case-sensitive, fails silently on uppercase |
| Dates `YYYY-MM-DD` | No time component |
| Putting = **feet**, else **yards** | `before_distance_yards` means feet on a putt |
| `handicap_index` float `0.0–54.0` | Not int, not string |
| Coach ~95s latency | Any added DB query or LLM call is a **taste decision** — escalate |

---

## What to Escalate (Don't Decide Alone)

- Latency and model choice (coach is already slow)
- Coach voice/tone
- Anything changing what the user sees or feels

Everything else — compilation, contract match, smoke test pass — answer yourself.

---

## Migrations

Applied **by hand** in Supabase SQL editor. `backend/migrations/` being present does not mean it ran. If you touch schema, say so loudly.

---

## Common Errors

| Error | Fix |
|-------|-----|
| `pydantic-core` build fails | Python 3.14 not supported. Use 3.12: `uv python install 3.12 && uv venv --python 3.12 && uv sync` |
| Smoke test fails with OpenAPI diff | Run `uv run python scripts/export_openapi.py` and commit |
| `uv` not found | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Server won't start | Check tmux `dimple-server`. Port 8000 may be held by old process. |

---

## This Week's Context (Aug 20, 2026)

- PR #18 merged — CI runs on every push/PR to Kanary
- Swift v1.0.0 is the goal. Expo is coach lab only.
- v1.0.0 blockers: course-selection fix verification, ManualCourseEntryView, device test, merge to main
- Coach streaming is next after v1.0.0 (biggest product problem: ~95s latency)

---

*Last updated: 2026-08-20*
