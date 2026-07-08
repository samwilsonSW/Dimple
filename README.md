# Dimple — AI Golf Coach

> **Your personal golf intelligence system.** Track rounds, analyze performance with strokes gained analytics, and get coached by an AI that knows your game.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![SwiftUI](https://img.shields.io/badge/SwiftUI-iOS%2017+-blue.svg)](https://developer.apple.com/xcode/swiftui/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What It Does

Dimple is a mobile-first golf tracking and coaching app:

1. **Find Courses** — Search 15,000+ courses, select tees, auto-load yardage/par
2. **Track Rounds** — Enter scores per hole (score, putts, fairway, GIR) with a sun-readable, one-handed interface
3. **View History** — See all rounds with strokes gained chips, trends, and stats
4. **Get Coached** — Ask the AI coach anything about your game. It retrieves your actual shots and gives personalized advice with drill recommendations

### Example Interaction

```
Player: "What should I work on?"

Coach: "You're hemorrhaging strokes with your hybrid from 175-185 yards.
Over 5 attempts, you've hit only one green (20% GIR) and found the rough 
on 60% of shots. The dispersion pattern suggests lateral dispersion is too 
wide for this club."

Drill: "The 6-Foot Gate Drill" — Place two alignment sticks 6 feet apart,
10 feet in front of your ball. Hit 20 hybrid shots through the gate.
Aim for 80% gate success before moving to targets.
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   iOS App       │───▶│  FastAPI     │────▶│  Supabase       │
│   (SwiftUI)     │     │  Backend     │     │  (Postgres +    │
│                 │◀────│              │◀────│   pgvector)     │
└─────────────────┘     └──────────────┘     └─────────────────┘
        │                      │
        │            ┌──────────────┐
        │            │  Local       │
        │            │  Embeddings  │
        │            │  (384-dim)   │
        │            └──────────────┘
        │                      │
        ▼                      ▼
┌─────────────────────────────────────────┐
│  Moonshot LLM (kimi-k2.5)               │
│  • RAG retrieval (top-5 similar shots)  │
│  • SG category aggregation              │
│  • Trend-based coaching                 │
│  • Structured JSON output               │
│  • Drill recommendations                │
└─────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Scorecard-first UX** | Low friction entry (score/putts/fairway/GIR) — rich shot-by-shot is the upgrade, not the gate |
| **Local embeddings** (all-MiniLM-L6-v2) | Zero API cost, 384-dim, fast enough for real-time |
| **Handicap-adjusted baselines** | A 15hcp's "good" drive is different from a 5hcp's — baselines scale 0-25 |
| **Vector search + LLM** | Retrieve similar shots for context, let LLM synthesize insights |
| **Synthetic round generator** | Generate realistic test data from Break X Golf statistics |

---

## Tech Stack

- **Frontend**: SwiftUI, iOS 17+
- **Backend**: FastAPI, Pydantic, SQLAlchemy
- **Database**: Supabase (Postgres + pgvector)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: Moonshot AI (kimi-k2.5) via OpenAI-compatible API
- **Analytics**: Custom strokes-gained engine with handicap interpolation
- **Testing**: Synthetic round generation from statistical distributions

---

## API Endpoints

### Search Courses
```bash
GET /api/v1/courses/search?q=Rawls&limit=10
```

### Ingest a Round (Scorecard Mode)
```bash
POST /api/v1/rounds
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "round_date": "2026-07-08",
  "course": {"name": "Rawls Course", "city": "Lubbock", "state": "TX"},
  "handicap_index": 15.2,
  "course_id": "21027",
  "tee_box": {"tee_name": "Blue", "rating": 74.9, "slope": 134},
  "hole_data": [
    {"hole_number": 1, "par": 4, "yardage": 402, "score": 5, "putts": 2, "fairway": true, "gir": false}
  ],
  "total_score": 85,
  "total_putts": 32
}
```

### Get Round History
```bash
GET /api/v1/rounds?user_id=550e8400-e29b-41d4-a716-446655440000&limit=50
```

### Ask the Coach
```bash
POST /api/v1/coach/ask
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "question": "How is my driving?"
}
```

**Response:**
```json
{
  "answer": "Your driving is elite—9/10 based on the data...",
  "confidence": 4,
  "key_insights": [
    "Tour-level SG: +0.48 per drive ranks in the 95th+ percentile",
    "Perfect accuracy: 5/5 fairways eliminates penalty strokes"
  ],
  "drill_recommendations": [
    {
      "priority": 1,
      "focus_area": "driver accuracy maintenance",
      "drill_name": "Fairway Gate Pressure Test",
      "instructions": "Place two alignment sticks 12-15 yards apart...",
      "expected_outcome": "Reinforces mechanical pattern producing accuracy"
    }
  ],
  "context": [...]
}
```

---

## Strokes Gained Methodology

Dimple implements a **handicap-adjusted strokes gained** system:

- **Baseline tables** for handicaps 0, 5, 10, 15, 20, 25 (interpolated for any value)
- **Per-shot SG**: Compares your result to expected strokes from that lie/distance
- **Category aggregation**: Driving, approach, short game, putting summaries
- **Statistical generator**: Synthetic rounds follow Break X Golf distributions

Example baseline (15hcp approach from fairway):
| Distance | Expected Strokes |
|----------|-----------------|
| 100 yards | 2.8 |
| 150 yards | 3.1 |
| 200 yards | 3.5 |

If you hit a 150-yard approach to 20 feet (expected 1.8 putts), your SG = 3.1 - (1 + 1.8) = +0.3 strokes gained.

---

## Project Structure

```
Dimple/
├── Dimple/                 # iOS SwiftUI app
│   ├── Views/              # CourseSearchView, ScorecardEntryView, RoundHistoryView
│   ├── Services/           # CourseService, RoundService, RoundHistoryService
│   ├── Models/             # Swift data models
│   └── DimpleApp.swift
├── backend/
│   ├── app/
│   │   ├── core/           # Generator, baselines, reflection logic
│   │   ├── models/         # Pydantic schemas (Shot, Round, CoachResponse)
│   │   ├── services/       # LLM client, embeddings, Supabase
│   │   └── main.py         # FastAPI app
│   ├── migrations/         # Schema evolution (001-015)
│   └── scripts/            # CLI tools, batch generation
├── data/
│   └── rounds/             # Sample rounds for testing
├── dimple_tui.py           # Interactive terminal for testing
├── docs/
│   ├── API_CONTRACT.md     # Backend ↔ Frontend interface
│   ├── TASK_BOARD.md       # What's in progress
│   ├── AGENT_STATUS.md     # Claude Code heartbeat
│   └── CHROLLO_ORCHESTRATION_PLAN.md  # How we work
└── README.md
```

---

## Running Locally

### Backend

```bash
# 1. Clone and setup
git clone https://github.com/samwilsonSW/Dimple.git
cd Dimple/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your Supabase and Moonshot API keys

# 3. Start server
python run.py

# 4. Test with TUI
python dimple_tui.py
```

### iOS App

Open `Dimple/Dimple.xcodeproj` in Xcode. Build and run on device or simulator.

**Note:** The app needs a reachable backend URL. For local development, run the backend on your machine and update the base URL in `CourseService.swift`. For production, deploy the backend (see below).

---

## What's Next

- [ ] **Shot-by-shot entry** — Full per-shot tracking (distance, lie, club, result) for power users
- [ ] **Round detail view** — Per-hole breakdown with map/visualization
- [ ] **Trend analysis** — Multi-round improvement tracking, handicap progression
- [ ] **Coach polish** — LLM-as-Judge evaluation, prompt refinement with real data
- [ ] **Deploy backend** — Fly.io or similar for production API access

## Product Principles

> **The real win:** Make scorecard mode so good that people *want* to upgrade to shot-by-shot because they see the value, not because we force them.
>
> Low friction first. Rich data as a reward, not a requirement.

---

## Why This Project

Most golf apps track scores. Dimple aims to help you improve your scores.

The technical challenge isn't just building a chatbot. It's:
- Designing a data model that captures enough context per shot
- Creating baselines that scale with player ability
- Using RAG to ground LLM advice in actual performance data
- Generating synthetic but statistically realistic test data

---

Built by [Sam Wilson](https://github.com/samwilsonSW) with help from [Kanary](https://github.com/openclaw) 🐤
