# Dimple Backend

FastAPI backend for Dimple Golf Intelligence app.

## Setup

### 1. Create virtual environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

### 4. Set up Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. Go to Project Settings → API
3. Copy **Project URL** and **service_role key** (NOT the anon key)
4. Paste into `.env`
5. Open SQL Editor and run:
   - `migrations/001_create_rounds_table.sql`
   - `migrations/002_create_vector_extension.sql`

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

API docs will be at `http://localhost:8000/docs`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/rounds` | Create new round |
| GET | `/rounds` | List rounds (summaries) |
| GET | `/rounds/{id}` | Get round details |
| PATCH | `/rounds/{id}` | Update round |
| DELETE | `/rounds/{id}` | Delete round |
| POST | `/rounds/{id}/holes` | Add hole |
| POST | `/rounds/{id}/holes/{n}/shots` | Add shot |
| POST | `/rounds/{id}/finish` | Finish round |

## Auth (Development)

For now, auth is simple: send `Authorization: Bearer <user_id>` header.
The backend uses the token as the user_id directly.

In production, replace with proper JWT validation from Supabase Auth.

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── core/
│   │   └── config.py        # Settings from .env
│   ├── models/
│   │   └── round.py         # Pydantic schemas
│   ├── routers/
│   │   ├── rounds.py        # Round API routes
│   │   └── health.py        # Health check
│   └── services/
│       ├── supabase_client.py  # Supabase connection
│       └── round_service.py    # Business logic
├── migrations/
│   ├── 001_create_rounds_table.sql
│   └── 002_create_vector_extension.sql
├── .env.example
├── requirements.txt
└── README.md
```

## Future: RAG / Vector Search

Migration `002` enables pgvector. When ready:

1. Create `shot_embeddings` table (see commented SQL)
2. Add embedding generation in `round_service.py`
3. Add `/rounds/{id}/analyze` endpoint for LLM insights
