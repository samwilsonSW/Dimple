# Synthetic Golf Round Data

Three synthetic rounds for testing the Dimple RAG pipeline.

## Players

| File | Handicap | Style | Score (approx) |
|------|----------|-------|----------------|
| `round_13hcp.json` | 13 | Solid amateur, occasional mistakes | ~85 |
| `round_29hcp.json` | 29 | Beginner, lots of topped shots, penalties, three-putts | ~120+ |
| `round_3hcp.json` | 3 | Elite amateur, near-professional ball-striking | ~61 |

## Course
All three rounds played at **Pine Valley Golf Club** (par 72, 6,800 yards).

## Hole Breakdown
Standard 72-par layout:
- Par 3s: Holes 3, 6, 12, 17
- Par 5s: Holes 5, 9, 15, 18
- Par 4s: All others

## Usage

Ingest via the API:

```bash
curl -X POST http://localhost:8000/api/v1/rounds \
  -H "Content-Type: application/json" \
  -d @data/rounds/round_13hcp.json
```

Then query the coach:

```bash
curl -X POST http://localhost:8000/api/v1/coach/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "player_13hcp", "question": "Why do I keep missing fairways?"}'
```
