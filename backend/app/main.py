from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

from app.core.config import get_settings
from app.models.round import RoundPayload, CoachQuery, CoachResponse, ShotModel
from app.services.supabase_client import get_supabase
from app.services.embeddings import embed_text, embed_texts
from app.services.llm import generate_coach_response

settings = get_settings()

app = FastAPI(
    title="Dimple API",
    description="Golf Intelligence Backend — Local Embeddings + Moonshot LLM",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ───────────────────────────────────────────────────────────────
# INGESTION ENDPOINT
# ───────────────────────────────────────────────────────────────

@app.post("/api/v1/rounds")
def ingest_round(payload: RoundPayload):
    """
    Accept a round payload, store metadata in `rounds`,
    embed each shot narrative locally via sentence-transformers,
    and bulk-insert into `shot_embeddings`.
    """
    supabase = get_supabase()

    # 1) Insert round metadata
    round_insert = {
        "user_id": payload.user_id,
        "round_date": payload.round_date,
        "course": payload.course,
    }
    result = supabase.table("rounds").insert(round_insert).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert round")

    round_id = result.data[0]["id"]

    # 2) Batch embed all shot narratives locally
    narratives = [shot.narrative for shot in payload.shots]
    try:
        vectors = embed_texts(narratives)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Local embedding failed: {str(e)}"
        )

    # 3) Build embeddings rows
    embeddings_rows: List[Dict[str, Any]] = []
    for shot, vector in zip(payload.shots, vectors):
        embeddings_rows.append({
            "shot_id": shot.shot_id,
            "round_id": round_id,
            "user_id": payload.user_id,
            "hole_number": shot.hole_number,
            "club": shot.club,
            "distance": shot.distance,
            "narrative": shot.narrative,
            "embedding": vector,
        })

    # 4) Bulk insert into shot_embeddings
    if embeddings_rows:
        embed_result = supabase.table("shot_embeddings").insert(embeddings_rows).execute()
        if not embed_result.data:
            raise HTTPException(status_code=500, detail="Failed to insert shot embeddings")

    return {
        "round_id": round_id,
        "shots_ingested": len(embeddings_rows),
        "status": "success",
    }


# ───────────────────────────────────────────────────────────────
# RAG COACH ENDPOINT
# ───────────────────────────────────────────────────────────────

@app.post("/api/v1/coach/ask", response_model=CoachResponse)
def coach_ask(query: CoachQuery):
    """
    RAG-based AI Coach:
    1. Embed the user's question locally
    2. Retrieve top-5 similar shots via Supabase RPC (cosine similarity)
    3. Build a prompt with retrieved context
    4. Call Moonshot LLM to generate a coaching response
    """
    supabase = get_supabase()

    # 1) Embed the question locally
    try:
        query_vector = embed_text(query.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Local embedding failed: {str(e)}")

    # 2) Retrieve top-5 similar shots via RPC
    try:
        rpc_result = supabase.rpc(
            "match_shots",
            {
                "query_embedding": query_vector,
                "match_user_id": query.user_id,
                "match_count": 5,
            }
        ).execute()
        similar_shots = rpc_result.data or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Supabase vector search failed: {str(e)}")

    # 3) Assemble context for the LLM
    context_blocks = []
    for i, shot in enumerate(similar_shots, 1):
        context_blocks.append(
            f"Shot {i}: {shot['narrative']} (Club: {shot['club']}, "
            f"Distance: {shot['distance']}y, Hole: {shot['hole_number']})"
        )

    context_text = "\n".join(context_blocks) if context_blocks else "No relevant shot history found."

    system_prompt = (
        "You are Dimple Coach, an expert golf coach. You have access to the player's "
        "historical shot data. Be direct, data-driven, and actionable. "
        "Ground every insight in the provided context. If you don't have enough data, say so."
    )

    user_prompt = (
        f"Player Question: {query.question}\n\n"
        f"Relevant Shot History:\n{context_text}\n\n"
        f"Based strictly on the shot history above, provide a helpful coaching response."
    )

    # 4) Call Moonshot LLM
    try:
        answer = generate_coach_response(system_prompt, user_prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")

    return CoachResponse(
        answer=answer,
        context=similar_shots,
    )
