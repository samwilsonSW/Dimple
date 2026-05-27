# Dimple — AI Golf Coach

> **Your personal golf intelligence system.** Track shots, analyze performance with strokes gained analytics, and get coached by an AI that knows your game.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## What It Does

Dimple turns your golf round data into actionable coaching insights:

1. **Track** — Log structured shot data (distance, lie, club, result)
2. **Analyze** — Calculate strokes gained vs. handicap-adjusted baselines
3. **Retrieve** — Find similar shots from your history via vector search
4. **Coach** — Get personalized advice, drills, and improvement plans from an LLM

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
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Player    │────▶│  FastAPI     │────▶│  Supabase       │
│  (Mobile)   │     │  Backend     │     │  (Postgres +    │
└─────────────┘     └──────────────┘     │   pgvector)     │
       │                   │              └─────────────────┘
       │                   │                       ▲
       │                   ▼                       │
       │            ┌──────────────┐              │
       │            │  Local       │              │
       │            │  Embeddings  │──────────────┘
       │            │  (384-dim)   │
       │            └──────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────────────┐
│  Moonshot LLM (kimi-k2.5)               │
│  • RAG retrieval (top-5 similar shots)  │
│  • SG category aggregation              │
│  • Structured JSON output               │
│  • Drill recommendations                │
└─────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Local embeddings** (all-MiniLM-L6-v2) | Zero API cost, 384-dim, fast enough for real-time |
| **Handicap-adjusted baselines** | A 15hcp's "good" drive is different from a 5hcp's — baselines scale 0-25 |
| **Structured shot input** | 5 fields per shot (distance, lie, club, result) — simple but rich |
| **Vector search + LLM** | Retrieve similar shots for context, let LLM synthesize insights |
| **Synthetic round generator** | Generate realistic test data from Break X Golf statistics |

---

## Tech Stack

- **Backend**: FastAPI, Pydantic, SQLAlchemy
- **Database**: Supabase (Postgres + pgvector)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: Moonshot AI (kimi-k2.5) via OpenAI-compatible API
- **Analytics**: Custom strokes-gained engine with handicap interpolation
- **Testing**: Synthetic round generation from statistical distributions

---

## API Endpoints

### Ingest a Round
```bash
POST /api/v1/rounds
{
  "user_id": "player_15hcp",
  "round_date": "2026-05-27",
  "course": {"name": "Pine Valley", "par": 71},
  "handicap_index": 15.2,
  "shots": [
    {
      "shot_id": "round_001_h1_s1",
      "hole_number": 1,
      "shot_number": 1,
      "before_distance_yards": 420,
      "before_lie": "T",
      "club": "D",
      "after_distance_yards": 166,
      "after_lie": "F",
      "strokes_taken": 1
    }
  ],
  "reflection": "Felt good off the tee today, struggled with approaches"
}
```

### Ask the Coach
```bash
POST /api/v1/coach/ask
{
  "user_id": "player_15hcp",
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
├── backend/
│   ├── app/
│   │   ├── core/           # Generator, baselines, reflection logic
│   │   ├── models/         # Pydantic schemas (Shot, Round, CoachResponse)
│   │   ├── services/       # LLM client, embeddings, Supabase
│   │   └── main.py         # FastAPI app
│   ├── migrations/         # Schema evolution (001-008)
│   └── scripts/            # CLI tools, batch generation
├── data/
│   └── rounds/             # Sample rounds for testing
├── dimple_tui.py           # Interactive terminal for testing
└── README.md
```

---

## Running Locally

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

---

## What's Next

- [ ] **Stats aggregation layer** — Broad questions ("How's my driving?") need aggregate stats, not just similar shots
- [ ] **LLM-as-Judge evaluation** — Automated quality scoring for coach responses
- [ ] **Mobile frontend** — PWA for shot logging and coach chat
- [ ] **Trend analysis** — Multi-round improvement tracking
- [ ] **Video integration** — Swing analysis alongside shot data

---

## Why This Project

Most golf apps track scores. Dimple tracks **why** you scored that way — and tells you how to fix it.

The technical challenge isn't just building a chatbot. It's:
- Designing a data model that captures enough context per shot
- Creating baselines that scale with player ability
- Using RAG to ground LLM advice in actual performance data
- Generating synthetic but statistically realistic test data

---

Built by [Sam Wilson](https://github.com/samwilsonSW) with help from [Kanary](https://github.com/openclaw) 🐤
