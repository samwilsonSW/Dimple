from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

from app.core.config import get_settings
from app.core.baselines import get_baseline_for_handicap
from app.models.round import RoundPayload, CoachQuery, CoachResponse, ShotModel, DrillRecommendation, LIE_CODES, CLUB_CODES
from app.services.supabase_client import get_supabase
from app.services.embeddings import embed_text, embed_texts
from app.services.llm import generate_coach_response, generate_structured_coach_response

settings = get_settings()

app = FastAPI(
    title="Dimple API",
    description="Golf Intelligence Backend — Local Embeddings + Moonshot LLM",
    version="0.5.0",
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


# ──────────────────────────────────────────────────────────────────────────────
# NARRATIVE GENERATOR
# ──────────────────────────────────────────────────────────────────────────────

def generate_shot_narrative(shot: ShotModel) -> str:
    """Auto-generate narrative from structured shot data for embedding.
    
    Format emphasizes distance TO the pin (not distance OF the shot)
    to avoid LLM confusion about shot length vs. remaining distance.
    """
    club_name = shot.club_full()
    
    # Before-state: distance to pin + lie
    before_lie_name = {
        "T": "tee",
        "F": "fairway",
        "R": "rough",
        "B": "bunker",
        "G": "green",
    }.get(shot.before_lie, shot.before_lie)
    
    if shot.before_lie == "T":
        before_phrase = f"{shot.before_distance_yards} yards to pin, tee shot"
    elif shot.before_lie == "G":
        before_phrase = "putt"
    else:
        before_phrase = f"{shot.before_distance_yards} yards to pin, in {before_lie_name}"

    # After-state: where the ball ended up
    if shot.after_lie == "HOLE":
        after_phrase = "holed"
    elif shot.after_lie == "T":
        after_phrase = "out of bounds, re-tee"
    elif shot.after_lie == "G" and shot.before_lie == "G":
        after_phrase = "missed"
    elif shot.after_lie == "G":
        after_phrase = "on green"
    elif shot.after_distance_yards is not None and shot.after_lie is not None:
        after_lie_name = LIE_CODES.get(shot.after_lie, shot.after_lie.lower())
        after_phrase = f"to {shot.after_distance_yards} yards to pin, in {after_lie_name}"
    else:
        after_phrase = "result pending"

    # Build narrative: "Club: [before] → [after]"
    narrative = f"{club_name}: {before_phrase} → {after_phrase}"

    if shot.strokes_taken > 1 and shot.before_lie != "G":
        narrative += f" (penalty: {shot.strokes_taken} strokes)"

    return narrative


# ──────────────────────────────────────────────────────────────────────────────
# INGESTION ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/rounds")
def ingest_round(payload: RoundPayload):
    """
    Accept a round payload with structured shot data.
    Auto-generates narratives, calculates SG, embeds, and stores.
    """
    supabase = get_supabase()

    # 1) Insert round metadata (including reflection if provided)
    round_insert = {
        "user_id": payload.user_id,
        "round_date": payload.round_date,
        "course": payload.course,
        "handicap_index": payload.handicap_index,
        "reflection": payload.reflection,
    }
    result = supabase.table("rounds").insert(round_insert).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert round")

    round_id = result.data[0]["id"]

    # 2) Auto-generate narratives for all shots
    shots_with_narrative: List[ShotModel] = []
    for shot in payload.shots:
        narrative = generate_shot_narrative(shot)
        shots_with_narrative.append(
            ShotModel(
                **shot.model_dump(exclude={"narrative"}),
                narrative=narrative,
            )
        )

    # 3) Batch embed all narratives locally
    narratives = [shot.narrative for shot in shots_with_narrative]
    try:
        vectors = embed_texts(narratives)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Local embedding failed: {str(e)}"
        )

    # 4) Calculate SG and build rows
    baseline = get_baseline_for_handicap(payload.handicap_index)
    embeddings_rows: List[Dict[str, Any]] = []

    # Pre-compute putting SG per hole
    # Group putts by hole, calculate hole-level putting SG
    putts_by_hole: Dict[int, List[ShotModel]] = {}
    for shot in shots_with_narrative:
        if shot.club == "P":
            putts_by_hole.setdefault(shot.hole_number, []).append(shot)
    
    putting_sg_by_hole: Dict[int, float] = {}
    for hole_num, putts in putts_by_hole.items():
        total_putts = len(putts)
        expected_putts = baseline.putts_per_hole()
        putting_sg_by_hole[hole_num] = expected_putts - total_putts

    for shot, vector in zip(shots_with_narrative, vectors):
        row: Dict[str, Any] = {
            "shot_id": shot.shot_id,
            "round_id": round_id,
            "user_id": payload.user_id,
            "hole_number": shot.hole_number,
            "shot_number": shot.shot_number,
            "before_distance_yards": shot.before_distance_yards,
            "before_lie_code": shot.before_lie,
            "before_lie": shot.before_lie_full(),
            "club_code": shot.club,
            "club": shot.club_full(),
            "after_distance_yards": shot.after_distance_yards,
            "after_lie_code": shot.after_lie,
            "after_lie": shot.after_lie_full(),
            "strokes_taken": shot.strokes_taken,
            "narrative": shot.narrative,
            "embedding": vector,
        }

        # Calculate SG if after-state is known
        after_lie_full = shot.after_lie_full()
        
        # Putting: hole-level SG assigned ONLY to the "holed" putt
        # Missed putts show no SG to avoid confusing the LLM
        if shot.club == "P":
            if shot.after_lie == "HOLE":
                sg = putting_sg_by_hole.get(shot.hole_number)
                if sg is not None:
                    row["sg_value"] = round(sg, 2)
            # Missed putts: no SG shown
        elif after_lie_full is not None and after_lie_full != "hole":
            # Non-putting, non-holed shot
            if shot.after_distance_yards is not None:
                try:
                    sg = baseline.sg(
                        before_distance=shot.before_distance_yards,
                        before_lie=shot.before_lie_full(),
                        after_distance=shot.after_distance_yards,
                        after_lie=after_lie_full,
                        strokes_taken=shot.strokes_taken,
                    )
                    row["sg_value"] = round(sg, 2)
                except Exception:
                    pass
        elif after_lie_full == "hole":
            # Non-putt holed out (chip-in, etc.)
            try:
                before = baseline.strokes(shot.before_distance_yards, shot.before_lie_full())
                sg = before - shot.strokes_taken
                row["sg_value"] = round(sg, 2)
            except Exception:
                pass

        embeddings_rows.append(row)

    # 5) Bulk insert into shot_embeddings
    if embeddings_rows:
        embed_result = supabase.table("shot_embeddings").insert(embeddings_rows).execute()
        if not embed_result.data:
            raise HTTPException(status_code=500, detail="Failed to insert shot embeddings")

    shots_with_sg = sum(1 for r in embeddings_rows if r.get("sg_value") is not None)

    return {
        "round_id": round_id,
        "shots_ingested": len(embeddings_rows),
        "shots_with_sg": shots_with_sg,
        "handicap_index": payload.handicap_index,
        "reflection_saved": payload.reflection is not None,
        "status": "success",
    }


# ──────────────────────────────────────────────────────────────────────────────
# RAG COACH ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

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

    # 3) Retrieve recent round reflections for this player
    try:
        reflections_result = supabase.table("rounds").select("round_date, reflection").eq("user_id", query.user_id).not_.is_("reflection", "null").order("round_date", desc=True).limit(3).execute()
        reflections = reflections_result.data or []
    except Exception:
        reflections = []

    reflection_text = ""
    if reflections:
        reflection_blocks = []
        for r in reflections:
            reflection_blocks.append(f"Round ({r['round_date']}): {r['reflection']}")
        reflection_text = "\n".join(reflection_blocks)

    # 4) Calculate SG category totals from retrieved shots
    sg_categories = {"driving": 0.0, "approach": 0.0, "short_game": 0.0, "putting": 0.0}
    category_counts = {"driving": 0, "approach": 0, "short_game": 0, "putting": 0}

    for shot in similar_shots:
        sg = shot.get("sg_value")
        if sg is None:
            continue
        lie = shot.get("before_lie", "")
        distance = shot.get("before_distance_yards")
        hole_num = shot.get("hole_number")
        
        # Per Broadie's "Every Shot Counts":
        # Inside 50 yards and not on green = short game
        # Tee shots on par 3 = approach, par 4/5 = driving
        if lie == "green":
            cat = "putting"
        elif distance is not None and distance < 50:
            cat = "short_game"
        elif lie == "tee":
            # Par 3 tee shots are approach, not driving
            from app.core.baselines import is_par3
            cat = "approach" if is_par3(hole_num) else "driving"
        elif lie in ("fairway", "rough", "sand", "hazard"):
            cat = "approach"
        else:
            cat = "approach"
        sg_categories[cat] += float(sg)
        category_counts[cat] += 1

    sg_summary_lines = []
    for cat, total in sg_categories.items():
        count = category_counts[cat]
        if count > 0:
            sg_summary_lines.append(f"{cat}: {total:+.2f} SG ({count} shots)")
    sg_summary = "\n".join(sg_summary_lines) if sg_summary_lines else "No SG data available."

    # 5) Assemble context for the LLM
    context_blocks = []
    for i, shot in enumerate(similar_shots, 1):
        sg_note = f" (SG: {shot['sg_value']:+.2f})" if shot.get('sg_value') is not None else ""
        context_blocks.append(
            f"Shot {i}: {shot['narrative']}{sg_note}"
        )

    context_text = "\n".join(context_blocks) if context_blocks else "No relevant shot history found."

    # Check for 25+ handicap — gently redirect to fundamentals
    try:
        player_result = supabase.table("rounds").select("handicap_index").eq("user_id", query.user_id).order("round_date", desc=True).limit(1).execute()
        player_handicap = player_result.data[0]["handicap_index"] if player_result.data else 0
    except Exception:
        player_handicap = 0
    
    if player_handicap >= 25:
        return CoachResponse(
            answer=(
                "At a 25+ handicap, the fastest path to improvement is building solid fundamentals: "
                "consistent contact, basic chipping, and two-putting. Once you're regularly breaking 100, "
                "we can dive into detailed analytics. For now, focus on: (1) hitting the range 2x/week, "
                "(2) short game practice, and (3) playing with purpose — pick one thing to work on each round."
            ),
            confidence=5,
            key_insights=[
                "25+ handicap: fundamentals over analytics",
                "Focus: consistent contact, basic chipping, two-putting",
                "Goal: regularly break 100 before detailed analysis",
            ],
            drill_recommendations=[
                DrillRecommendation(
                    priority=1,
                    focus_area="fundamentals",
                    drill_name="7-Iron Consistency",
                    instructions="Hit 20 7-irons focusing on solid contact. Don't worry about distance, just crisp strikes.",
                    expected_outcome="Clean contact 80% of the time",
                ),
                DrillRecommendation(
                    priority=2,
                    focus_area="short game",
                    drill_name="Chip-and-Putt",
                    instructions="Drop 5 balls 10 yards off the green. Chip to hole, then putt. Repeat 3 times.",
                    expected_outcome="Get up-and-down 2 out of 5 times",
                ),
            ],
            context=[],
        )

    system_prompt = (
        "You are Dimple Coach, an expert golf coach. You have access to the player's "
        "historical shot data with Strokes Gained values. Be direct, data-driven, and actionable. "
        "Ground every insight in the provided context. If you don't have enough data, say so."
    )

    user_prompt_parts = [
        f"Player Question: {query.question}",
        "",
        "Strokes Gained Summary (from retrieved shots):",
        sg_summary,
        "",
        "Relevant Shot History:",
        context_text,
    ]

    if reflection_text:
        user_prompt_parts.extend([
            "",
            "Player's Recent Round Reflections:",
            reflection_text,
        ])

    user_prompt_parts.extend([
        "",
        "Based on the shot history, SG summary, and any player reflections above, provide a helpful coaching response. "
        "Connect the quantitative data (SG) with the qualitative observations (reflections) when both are available."
    ])

    user_prompt = "\n".join(user_prompt_parts)

    # 4) Call Moonshot LLM (structured JSON)
    try:
        structured = generate_structured_coach_response(system_prompt, user_prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")

    # Build drill objects from parsed JSON
    drills = []
    for d in structured.get("drill_recommendations", []):
        drills.append(DrillRecommendation(
            priority=d.get("priority", 1),
            focus_area=d.get("focus_area", ""),
            drill_name=d.get("drill_name", ""),
            instructions=d.get("instructions", ""),
            expected_outcome=d.get("expected_outcome", ""),
        ))

    return CoachResponse(
        answer=structured.get("answer", ""),
        confidence=structured.get("confidence", 3),
        key_insights=structured.get("key_insights", []),
        drill_recommendations=drills,
        context=similar_shots,
    )
