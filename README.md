# Dimple

**A golf tracker with a coach attached.** Log a round hole by hole, and an LLM
grounded in your own shot history tells you where the strokes went.

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)
![SwiftUI](https://img.shields.io/badge/SwiftUI-iOS%2026.5+-orange.svg)
![Expo](https://img.shields.io/badge/Expo-SDK%2054-000020.svg)

Most golf apps record what you shot. Dimple tries to explain it — by measuring
every round against baselines for *your* handicap, not a tour pro's, and by
giving the coach real retrieved shots to reason over instead of vibes.

---

## What it does

**Search a course** — Course lookup and tee selection via GolfCourseAPI.com,
which auto-fills per-hole par and yardage. Courses the API doesn't have can be
entered by hand.

**Track a round** — Per-hole entry: score, putts, fairway, green in regulation.
One-handed, high-contrast, autosaving, and it survives the app being killed
mid-round.

**See the history** — Every round with strokes-gained figures, putting and
approach splits, GIR and fairway percentages.

**Ask the coach** — A conversational coach that retrieves your five most
similar past shots by vector search, aggregates your strokes-gained trends, and
returns structured advice with ranked drill recommendations.

---

## Architecture

```
  SwiftUI app  ─┐
                ├─▶  FastAPI  ─▶  Supabase (Postgres + pgvector)
  Expo app     ─┘       │
                        ├─▶  sentence-transformers  (local, 384-dim)
                        └─▶  Moonshot kimi-k2.5     (coaching)
```

Shot narratives are embedded **locally** with `all-MiniLM-L6-v2` — no per-shot
API cost, and the vectors live in Postgres via pgvector. When you ask the coach
something, the backend embeds the question, pulls the five nearest shots via a
`match_shots` Postgres function, folds in aggregate strokes-gained stats, and
hands the LLM a grounded prompt. The response comes back as structured JSON,
not prose to be parsed. The prompt adapts to what data actually exists, so a
new user gets a coach that admits it hasn't seen them play yet.

---

## Strokes gained, handicap-adjusted

This is the part that isn't a wrapper around an API.

A 15-handicap hitting a 150-yard approach to 20 feet did something *good*. The
same shot from a scratch player is unremarkable. Dimple keeps separate baseline
tables for handicaps 0, 5, 10, 15, 20, and 25, and linearly interpolates between
brackets for anything in between — so you're always measured against your peers.

Baselines are derived from Broadie's *Every Shot Counts* amateur data for
scratch, calibrated against Break X Golf's aggregate statistics (3,788 rounds
across 1,116 golfers) for the rest.

```
SG = Baseline(before) − strokes_taken − Baseline(after)
```

A worked example, 15 handicap:

| | |
|---|---|
| 150 yards, fairway | baseline **2.85** strokes to hole out |
| you hit it to 20 feet | that's 1 stroke |
| 20 feet, green | baseline **1.68** strokes to hole out |
| **SG** | 2.85 − 1 − 1.68 = **+0.17** |

Slightly better than a 15-handicap would typically do. Every shot gets this
treatment, then aggregates into putting, approach, driving, and short-game
splits.

The engine is ~750 lines of pure Python in `backend/app/core/` with no
third-party imports — it's the part of the product that has to be right.

---

## Tech stack

| Layer | Choice |
|---|---|
| iOS client | SwiftUI, iOS 26.5+ |
| Second client | Expo / React Native (SDK 54) |
| API | FastAPI + Pydantic v2 |
| Database | Supabase — Postgres + pgvector |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2`, 384-dim, run locally |
| LLM | Moonshot `kimi-k2.5` via an OpenAI-compatible client |
| Auth | Supabase Auth |
| Hosting | Cloudflare named tunnel |
| Dependencies | uv, fully locked |

**Why two clients.** `frontend/` is the SwiftUI app — the whole tracker, ~4,800
lines: auth, course search, scorecard entry, round history, handicap. `mobile/`
is a smaller Expo client, ~900 lines, covering login and the coach chat only.
It exists because the coach is the part that needs constant iteration, and
pushing a JavaScript bundle to a phone takes seconds where an Xcode build and
install takes minutes. Both talk to the same API.

---

## API

```
GET   /health
GET   /api/v1/courses/search?q=...
GET   /api/v1/courses/{course_id}
POST  /api/v1/rounds
GET   /api/v1/rounds?user_id=...
POST  /api/v1/coach/chat
GET   /api/v1/coach/conversations
GET   /api/v1/coach/conversations/{id}/messages
```

A coach reply carries `answer`, a `confidence` score, `key_insights`, and
`drill_recommendations` — each with a priority, focus area, instructions, and
an expected outcome.

Request and response schemas are **generated from the Pydantic models** into
[`docs/openapi.json`](docs/openapi.json) rather than written by hand, and CI
fails if the committed schema drifts from the code.

---

## Running it

Backend — requires [uv](https://docs.astral.sh/uv/) and Python 3.12+:

```bash
cd backend
cp .env.example .env          # Supabase + Moonshot + GolfCourseAPI keys
uv run python run.py          # uv syncs .venv from uv.lock automatically
```

There's no virtualenv to activate and no `pip install` step.

iOS — open `frontend/dimple-frontend.xcodeproj`, copy
`frontend/Secrets.xcconfig.example` to `Secrets.xcconfig` and add your Supabase
publishable key, then build.

Expo — `cd mobile && npm install && npx expo start`.

### Verifying a change

```bash
cd backend && uv run python scripts/smoke_test.py           # offline
cd backend && uv run python scripts/smoke_test.py --live    # against a server
```

The offline tier needs no credentials, no network, and no running server. It
checks that the committed OpenAPI schema matches the code and that the contract's
validation rules still hold. It runs on every push and pull request.

---

## Project layout

```
backend/
  app/core/        strokes-gained baselines, round stats, synthetic generator
  app/models/      Pydantic schemas — the API contract in code
  app/services/    embeddings, LLM, Supabase, course API
  app/routers/     course search
  migrations/      SQL, applied by hand
  scripts/         schema export, tiered smoke test
frontend/          SwiftUI iOS app
mobile/            Expo / React Native coach client
docs/
  API_CONTRACT.md  endpoint semantics, error meanings, known risks
  openapi.json     generated schemas — authoritative
  STATUS.md        what works right now
AGENTS.md          repo conventions and landmines
```
---

Built by [Sam Wilson](https://github.com/samwilsonSW).
