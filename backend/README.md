# Dimple Backend

FastAPI backend for Dimple Golf Intelligence — RAG ingestion & AI Coach.

## Stack

- **FastAPI** + **uvicorn**
- **Supabase** (Postgres + pgvector)
- **sentence-transformers** (local embeddings, all-MiniLM-L6-v2, 384-dim)
- **Moonshot API** (LLM generation, kimi-k2.5)

## Quick Start

### 1. Clone & navigate

```bash
git clone https://github.com/samwilsonSW/Dimple.git
cd Dimple
git checkout feature/rag-ingestion-coach
```

### 2. Create virtual environment

**macOS/Linux:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** First run downloads ~80MB `all-MiniLM-L6-v2` model to `~/.cache/torch/sentence_transformers`

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
MOONSHOT_API_KEY=sk-your-moonshot-key
```

### 5. Run database migrations

In Supabase SQL Editor, run in order:
1. `migrations/001_create_rounds_table.sql`
2. `migrations/002_create_vector_extension.sql`
3. `migrations/003_create_shot_embeddings.sql` (or `004_recreate_shot_embeddings_384.sql` for 384-dim)

### 6. Start the server

**Option A: From project root (recommended)**
```bash
cd ..  # back to project root
python run.py
```

**Option B: From backend folder**
```bash
python run.py
```

**Option C: Direct uvicorn (if PYTHONPATH is set)**
```bash
# macOS/Linux:
PYTHONPATH=$(pwd)/.. uvicorn backend.app.main:app --reload

# Windows:
set PYTHONPATH=%CD%\..
python -m uvicorn backend.app.main:app --reload
```

### 7. Verify

```bash
curl http://localhost:8000/health
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/rounds` | Ingest round + embed shots |
| POST | `/api/v1/coach/ask` | RAG coach query |

## Testing with Synthetic Data

```bash
# Ingest a round
curl -X POST http://localhost:8000/api/v1/rounds \
  -H "Content-Type: application/json" \
  -d @data/rounds/round_13hcp.json

# Ask the coach
curl -X POST http://localhost:8000/api/v1/coach/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "player_13hcp", "question": "Why do I keep missing fairways?"}'
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py        # Settings from .env
│   ├── models/
│   │   ├── __init__.py
│   │   └── round.py         # Pydantic schemas
│   └── services/
│       ├── __init__.py
│       ├── embeddings.py    # Local embedding model
│       ├── llm.py           # Moonshot client
│       └── supabase_client.py
├── migrations/
│   ├── 001_create_rounds_table.sql
│   ├── 002_create_vector_extension.sql
│   ├── 003_create_shot_embeddings.sql
│   └── 004_recreate_shot_embeddings_384.sql
├── .env.example
├── requirements.txt
└── run.py                   # Entry point
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'backend'`**
→ Use `python run.py` from the project root. The `run.py` script handles the Python path.

**`ModuleNotFoundError: No module named 'app'`**
→ Don't run `uvicorn app.main:app` directly. Use `python run.py` instead.

**Model download hangs**
→ The first run downloads `all-MiniLM-L6-v2` (~80MB). If it hangs, check your internet connection or manually download it.

**Supabase connection fails**
→ Make sure you're using the **service_role key** (not anon key) and have run all migrations.
