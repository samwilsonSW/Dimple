from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import threading

from app.core.config import get_settings
from app.core.baselines import get_baseline_for_handicap
from app.core.scorecard_stats import calculate_round_stats
from app.models.round import (
    RoundPayload, CoachQuery, CoachResponse, CoachChatRequest, CoachChatResponse,
    Message, ConversationSummary, ShotModel, DrillRecommendation, LIE_CODES, CLUB_CODES
)
from app.services.supabase_client import get_supabase
from app.services.embeddings import embed_text, embed_texts
from app.services.llm import generate_coach_response, generate_structured_coach_response
from app.services.title_generator import generate_title
from app.routers import courses

settings = get_settings()

app = FastAPI(
    title="Dimple API",
    description="Golf Intelligence Backend — Local Embeddings + Moonshot LLM",
    version="1.1.0",
)

app.include_router(courses.router)


@app.on_event("startup")
def warm_embedding_model():
    """Warm the embedding model in the background when the server boots.

    The model loads lazily at module level so that importing the app stays free
    — CI, schema export and the smoke test never need it. But a long-lived
    server wants it warm, or the first coach request after a restart pays the
    load on top of already-slow coach latency.

    Runs on a daemon thread so boot never blocks: if huggingface.co is slow or
    unreachable, `HF_HUB_DOWNLOAD_TIMEOUT` is 300s and we must not hold /health
    hostage to it. A request arriving mid-warmup just waits on the same lock.
    """
    def _warm():
        from app.services.embeddings import get_model

        try:
            get_model()
        except Exception as exc:  # noqa: BLE001 — never take the server down
            print(f"[startup] embedding model warmup failed, will retry on demand: {exc}")

    threading.Thread(target=_warm, name="embed-warmup", daemon=True).start()


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

    # 1) Insert round metadata (including reflection and manual_course if provided)
    round_insert = {
        "user_id": payload.user_id,
        "round_date": payload.round_date,
        "course": payload.course,
        "handicap_index": payload.handicap_index,
        "reflection": payload.reflection,
    }
    # Add manual_course JSONB if present (mutually exclusive with course_id)
    if payload.manual_course:
        round_insert["manual_course"] = payload.manual_course.model_dump()
    result = supabase.table("rounds").insert(round_insert).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to insert round")

    round_id = result.data[0]["id"]

    # 2) Auto-generate narratives for all shots
    # `shots` is optional — scorecard-only submissions (hole_data) omit it.
    shots_with_narrative: List[ShotModel] = []
    for shot in (payload.shots or []):
        narrative = generate_shot_narrative(shot)
        shots_with_narrative.append(
            ShotModel(
                **shot.model_dump(exclude={"narrative"}),
                narrative=narrative,
            )
        )

    # 3) Batch embed all narratives locally (skip entirely in scorecard-only mode)
    narratives = [shot.narrative for shot in shots_with_narrative]
    vectors = []
    if narratives:
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

    # Persist the raw per-hole entries.
    #
    # These used to be consumed for stats and thrown away, which meant no round
    # could ever be recomputed — every model improvement applied only to future
    # rounds while history stayed wrong. Storing them is what makes the
    # strokes-gained rebuild retroactive. Failure here must not lose the round.
    holes_stored = 0
    if payload.hole_data:
        try:
            supabase.table("hole_scores").insert([
                {
                    "round_id": round_id,
                    "user_id": payload.user_id,
                    "hole_number": h.hole_number,
                    "par": h.par,
                    "yardage": h.yardage,
                    "score": h.score,
                    "putts": h.putts,
                    "fairway": h.fairway,
                    "gir": h.gir,
                    "first_putt": h.first_putt,
                    "penalty_strokes": h.penalty_strokes,
                }
                for h in payload.hole_data
            ]).execute()
            holes_stored = len(payload.hole_data)
        except Exception as e:
            print(f"Warning: Failed to store hole scores: {e}")

    # Calculate scorecard stats if hole_data provided
    round_stats = None
    if payload.hole_data:
        try:
            # For manual courses, use provided par_values for strokes_over_under
            manual_par_values = None
            if payload.manual_course:
                manual_par_values = payload.manual_course.par_values
            
            stats = calculate_round_stats(
                hole_data=payload.hole_data,
                handicap=payload.handicap_index,
                course_rating=payload.tee_box.rating if payload.tee_box else None,
                course_slope=payload.tee_box.slope if payload.tee_box else None,
                manual_par_values=manual_par_values,
            )
            stats_row = {
                "round_id": str(round_id),
                "user_id": payload.user_id,
                **stats,
            }
            supabase.table("round_stats").insert(stats_row).execute()
            round_stats = stats
        except Exception as e:
            # Don't fail ingestion if stats calc fails
            print(f"Warning: Failed to calculate round stats: {e}")

    response = {
        "round_id": round_id,
        "shots_ingested": len(embeddings_rows),
        "shots_with_sg": shots_with_sg,
        "handicap_index": payload.handicap_index,
        "reflection_saved": payload.reflection is not None,
        "holes_stored": holes_stored,
        "status": "success",
    }
    if round_stats:
        response["round_stats"] = round_stats
    
    return response


# ──────────────────────────────────────────────────────────────────────────────
# DATA INVENTORY
# ──────────────────────────────────────────────────────────────────────────────

def build_data_inventory(supabase, user_id: str) -> Dict[str, Any]:
    """Query what data exists for a player before building the coach prompt."""
    inventory = {
        "round_stats_count": 0,
        "shot_embeddings_count": 0,
        "reflections_count": 0,
        "has_round_stats": False,
        "has_trends": False,
        "has_shots": False,
        "has_reflections": False,
    }
    
    try:
        # Count round_stats
        result = supabase.table("round_stats").select("id", count="exact").eq("user_id", user_id).execute()
        inventory["round_stats_count"] = result.count or 0
        inventory["has_round_stats"] = inventory["round_stats_count"] > 0
        inventory["has_trends"] = inventory["round_stats_count"] >= 3
    except Exception:
        pass
    
    try:
        # Count shot_embeddings
        result = supabase.table("shot_embeddings").select("id", count="exact").eq("user_id", user_id).execute()
        inventory["shot_embeddings_count"] = result.count or 0
        inventory["has_shots"] = inventory["shot_embeddings_count"] > 0
    except Exception:
        pass
    
    try:
        # Count reflections
        result = supabase.table("rounds").select("id", count="exact").eq("user_id", user_id).not_.is_("reflection", "null").execute()
        inventory["reflections_count"] = result.count or 0
        inventory["has_reflections"] = inventory["reflections_count"] > 0
    except Exception:
        pass
    
    return inventory


def fetch_round_stats_summary(supabase, user_id: str, limit: int = 3) -> str:
    """Fetch recent round stats for the prompt."""
    try:
        result = supabase.table("round_stats").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        stats = result.data or []
    except Exception:
        return ""
    
    if not stats:
        return ""
    
    lines = [f"Recent Round Stats (last {len(stats)} rounds):"]
    for i, s in enumerate(stats, 1):
        lines.append(
            f"Round {i}: Score {s['total_score']}, GIR {s['gir_percentage']:.0%}, "
            f"Fairway {s['fairway_percentage']:.0%}, Putts {s['total_putts']}, "
            f"SG Putting {s['sg_putting']:+.1f}, SG Approach {s['sg_approach']:+.1f}"
        )
    return "\n".join(lines)


def fetch_trend_summary(supabase, user_id: str) -> str:
    """Fetch trend summary using get_trend_summary from scorecard_stats."""
    try:
        result = supabase.table("round_stats").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        stats = result.data or []
    except Exception:
        return ""
    
    if len(stats) < 3:
        return ""
    
    from app.core.scorecard_stats import get_trend_summary
    trends = get_trend_summary(stats, num_rounds=5)
    
    if not trends:
        return ""
    
    lines = [
        f"Trends (last {trends['rounds_analyzed']} rounds):",
        f"  Avg GIR: {trends['avg_gir_percentage']:.0%}",
        f"  Avg Fairway: {trends['avg_fairway_percentage']:.0%}",
        f"  Avg Putts: {trends['avg_putts_per_round']:.1f}",
        f"  Avg SG Putting: {trends['avg_sg_putting']:+.2f}",
        f"  Avg SG Approach: {trends['avg_sg_approach']:+.2f}",
        f"  Trend: {trends['trend_direction']}",
    ]
    return "\n".join(lines)


def fetch_shot_history(supabase, user_id: str, question: str) -> tuple:
    """Fetch similar shots via RAG. Returns (shots, sg_summary)."""
    try:
        query_vector = embed_text(question)
    except Exception:
        return [], "No SG data available."
    
    try:
        rpc_result = supabase.rpc(
            "match_shots",
            {
                "query_embedding": query_vector,
                "match_user_id": user_id,
                "match_count": 5,
            }
        ).execute()
        similar_shots = rpc_result.data or []
    except Exception:
        return [], "No SG data available."
    
    # Calculate SG categories
    sg_categories = {"driving": 0.0, "approach": 0.0, "short_game": 0.0, "putting": 0.0}
    category_counts = {"driving": 0, "approach": 0, "short_game": 0, "putting": 0}

    for shot in similar_shots:
        sg = shot.get("sg_value")
        if sg is None:
            continue
        lie = shot.get("before_lie", "")
        distance = shot.get("before_distance_yards")
        hole_num = shot.get("hole_number")
        
        if lie == "green":
            cat = "putting"
        elif distance is not None and distance < 50:
            cat = "short_game"
        elif lie == "tee":
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
    
    return similar_shots, sg_summary


def fetch_reflections(supabase, user_id: str, limit: int = 3) -> str:
    """Fetch recent round reflections."""
    try:
        result = supabase.table("rounds").select("round_date, reflection").eq("user_id", user_id).not_.is_("reflection", "null").order("round_date", desc=True).limit(limit).execute()
        reflections = result.data or []
    except Exception:
        return ""
    
    if not reflections:
        return ""
    
    blocks = []
    for r in reflections:
        blocks.append(f"Round ({r['round_date']}): {r['reflection']}")
    return "\n".join(blocks)


def build_system_prompt(inventory: Dict[str, Any]) -> str:
    """Build adaptive system prompt based on data inventory."""
    parts = ["You are Dimple Coach, an expert golf coach."]
    
    # Data disclaimer
    if inventory["has_round_stats"] and inventory["has_shots"]:
        parts.append(
            f"This player has {inventory['round_stats_count']} rounds of scorecard data "
            f"(scores, GIR, fairways, putts) and {inventory['shot_embeddings_count']} shots with detailed tracking."
        )
    elif inventory["has_round_stats"]:
        parts.append(
            f"This player has {inventory['round_stats_count']} rounds of scorecard data "
            f"(scores, GIR, fairways, putts). No detailed shot tracking yet."
        )
    elif inventory["has_shots"]:
        parts.append(
            f"This player has {inventory['shot_embeddings_count']} shots with detailed tracking. "
            f"No scorecard rounds logged yet."
        )
    else:
        parts.append("This player has no rounds logged yet.")
    
    if inventory["has_shots"]:
        parts.append("You have access to historical shot data with Strokes Gained values.")
    
    parts.append(
        "You are conversational and direct. When you don't have enough data for a definitive "
        "answer, ask the player one focused follow-up question to fill the gap. Use their "
        "answer along with any available stats to give actionable advice. Never give generic "
        "fundamentals advice unless the player explicitly asks for it."
    )
    
    parts.append(
        "Be data-driven and actionable. Ground every insight in the provided context. "
        "If you don't have enough data, say so and suggest what to track."
    )
    
    return "\n\n".join(parts)


def build_user_prompt(
    question: str,
    inventory: Dict[str, Any],
    round_stats_text: str,
    trend_text: str,
    shot_history_text: str,
    sg_summary: str,
    reflection_text: str,
    conversation_history: List[Dict[str, str]] = None,
) -> str:
    """Build user prompt with conditional sections."""
    parts = [f"Player Question: {question}", ""]
    
    # Conversation history
    if conversation_history:
        parts.append("Previous messages in this conversation:")
        for msg in conversation_history:
            role = "Player" if msg["role"] == "user" else "Coach"
            parts.append(f"{role}: {msg['content']}")
        parts.append("")
    
    # Scorecard summary
    if round_stats_text and inventory["has_round_stats"]:
        parts.extend([round_stats_text, ""])
    
    # Trends
    if trend_text and inventory["has_trends"]:
        parts.extend([trend_text, ""])
    
    # Shot history and SG (only if shots exist)
    if inventory["has_shots"]:
        parts.extend([
            "Strokes Gained Summary (from retrieved shots):",
            sg_summary,
            "",
            "Relevant Shot History:",
            shot_history_text,
            "",
        ])
    
    # Reflections
    if reflection_text and inventory["has_reflections"]:
        parts.extend([
            "Player's Recent Round Reflections:",
            reflection_text,
            "",
        ])
    
    # Instruction
    parts.append(
        "Based on the available data above, provide a helpful coaching response. "
        "Prioritize trend-based insights from the round stats when available. "
        "Connect quantitative data with qualitative observations. "
        "If data is limited, ask one focused follow-up question to better understand the player's situation."
    )
    
    return "\n".join(parts)


def determine_confidence(inventory: Dict[str, Any]) -> int:
    """Determine confidence level based on data richness."""
    if inventory["has_shots"] and inventory["has_trends"]:
        return 5  # Rich shot + trend data
    elif inventory["has_shots"]:
        return 4  # With shot data
    elif inventory["has_trends"]:
        return 3  # 5+ rounds, no shots
    elif inventory["has_round_stats"]:
        return 2  # 1-2 rounds
    else:
        return 1  # No data


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATIONAL COACH ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

import time
import logging

logger = logging.getLogger(__name__)


@app.post("/api/v1/coach/chat", response_model=CoachChatResponse)
def coach_chat(request: CoachChatRequest):
    """
    Conversational AI Coach:
    1. Build data inventory (what data exists for this player)
    2. Fetch conditional data (round stats, trends, shots, reflections)
    3. Build adaptive prompt based on inventory
    4. Call Moonshot LLM to generate coaching response
    5. Save conversation and messages to database
    """
    request_start = time.time()
    supabase = get_supabase()
    
    # 1) Get or create conversation
    conversation_id = request.conversation_id
    if conversation_id:
        # Verify conversation exists and belongs to user
        # NOTE: Made non-fatal — transient Supabase timeouts shouldn't kill the chat
        verify_start = time.time()
        try:
            conv_result = supabase.table("conversations").select("*").eq("id", conversation_id).eq("user_id", request.user_id).single().execute()
            if not conv_result.data:
                raise HTTPException(status_code=404, detail="Conversation not found")
        except HTTPException:
            raise
        except Exception as e:
            verify_elapsed = time.time() - verify_start
            logger.warning(
                f"Conversation verify timeout/Error for conv_id={conversation_id} "
                f"after {verify_elapsed:.2f}s: {str(e)}. "
                f"Continuing without strict verification — user_id match is sufficient."
            )
            # Non-fatal: assume the conversation exists and belongs to the user
            # The frontend only sends conversation_ids it already knows about
            pass
    else:
        # Create new conversation
        title = "Coach Chat"
        if request.round_id:
            # Get round info for title — non-fatal if this fails
            try:
                round_result = supabase.table("rounds").select("course, round_date").eq("id", request.round_id).single().execute()
                if round_result.data:
                    course_name = round_result.data.get("course", {}).get("name", "Unknown Course")
                    round_date = round_result.data.get("round_date", "")
                    title = f"Round at {course_name} — {round_date}"
            except Exception as e:
                logger.warning(f"Round lookup failed for round_id={request.round_id}: {e}. Using default title.")
        
        try:
            conv_result = supabase.table("conversations").insert({
                "user_id": request.user_id,
                "round_id": request.round_id,
                "title": title,
            }).execute()
            conversation_id = conv_result.data[0]["id"]
        except Exception as e:
            # If the round_id FK constraint fails, retry with round_id=NULL
            # so the user can still chat even if the round was deleted.
            if request.round_id and "23503" in str(e):
                logger.warning(
                    f"FK violation on conversations.round_id={request.round_id}: {e}. "
                    f"Retrying with round_id=NULL."
                )
                try:
                    conv_result = supabase.table("conversations").insert({
                        "user_id": request.user_id,
                        "round_id": None,
                        "title": title,
                    }).execute()
                    conversation_id = conv_result.data[0]["id"]
                except Exception as e2:
                    raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e2)}")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to create conversation: {str(e)}")
    
    # 2) Fetch conversation history (last 6 messages)
    conversation_history = []
    try:
        msgs_result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=True).limit(6).execute()
        if msgs_result.data:
            # Reverse to get chronological order
            conversation_history = [
                {"role": m["role"], "content": m["content"]} 
                for m in reversed(msgs_result.data)
            ]
    except Exception:
        pass
    
    # 3) Save user message
    try:
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "user",
            "content": request.message,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")
    
    # 3b) Generate title for new conversations (fire-and-forget, non-blocking)
    is_new_conversation = request.conversation_id is None
    if is_new_conversation:
        try:
            generated_title = generate_title(request.message)
            if generated_title:
                supabase.table("conversations").update({
                    "title": generated_title
                }).eq("id", conversation_id).execute()
                logger.info(f"Generated title for conv {conversation_id}: '{generated_title}'")
        except Exception as e:
            # Non-fatal: title generation failure shouldn't break the chat
            logger.warning(f"Title generation failed for conv {conversation_id}: {e}")
    
    # 4) Build data inventory
    inventory = build_data_inventory(supabase, request.user_id)
    
    # 5) Fetch conditional data
    round_stats_text = fetch_round_stats_summary(supabase, request.user_id) if inventory["has_round_stats"] else ""
    trend_text = fetch_trend_summary(supabase, request.user_id) if inventory["has_trends"] else ""
    
    similar_shots = []
    sg_summary = "No SG data available."
    shot_history_text = "No relevant shot history found."
    
    if inventory["has_shots"]:
        similar_shots, sg_summary = fetch_shot_history(supabase, request.user_id, request.message)
        context_blocks = []
        for i, shot in enumerate(similar_shots, 1):
            sg_note = f" (SG: {shot['sg_value']:+.2f})" if shot.get('sg_value') is not None else ""
            context_blocks.append(f"Shot {i}: {shot['narrative']}{sg_note}")
        shot_history_text = "\n".join(context_blocks) if context_blocks else "No relevant shot history found."
    
    reflection_text = fetch_reflections(supabase, request.user_id) if inventory["has_reflections"] else ""
    
    # 6) Build prompts
    system_prompt = build_system_prompt(inventory)
    user_prompt = build_user_prompt(
        question=request.message,
        inventory=inventory,
        round_stats_text=round_stats_text,
        trend_text=trend_text,
        shot_history_text=shot_history_text,
        sg_summary=sg_summary,
        reflection_text=reflection_text,
        conversation_history=conversation_history,
    )
    
    # 7) Call LLM
    llm_start = time.time()
    try:
        structured = generate_structured_coach_response(system_prompt, user_prompt)
    except Exception as e:
        llm_elapsed = time.time() - llm_start
        logger.error(f"LLM generation failed after {llm_elapsed:.2f}s: {str(e)}")
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)}")
    llm_elapsed = time.time() - llm_start
    
    # 8) Build response
    answer = structured.get("answer", "")
    confidence = structured.get("confidence", determine_confidence(inventory))
    key_insights = structured.get("key_insights", [])
    
    drills = []
    for d in structured.get("drill_recommendations", []):
        drills.append(DrillRecommendation(
            priority=d.get("priority", 1),
            focus_area=d.get("focus_area", ""),
            drill_name=d.get("drill_name", ""),
            instructions=d.get("instructions", ""),
            expected_outcome=d.get("expected_outcome", ""),
        ))
    
    # 9) Save assistant message
    try:
        supabase.table("messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": answer,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save assistant message: {str(e)}")
    
    # 10) Return response with timing
    total_elapsed = time.time() - request_start
    logger.info(
        f"Coach chat completed: conv_id={conversation_id}, "
        f"llm_time={llm_elapsed:.2f}s, total_time={total_elapsed:.2f}s, "
        f"data_inventory={inventory}"
    )
    
    return CoachChatResponse(
        conversation_id=conversation_id,
        message=Message(
            role="assistant",
            content=answer,
        ),
        answer=answer,
        confidence=confidence,
        key_insights=key_insights,
        drill_recommendations=drills,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSATION LIST ENDPOINTS
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/coach/conversations")
def get_conversations(user_id: str, limit: int = 10):
    """List conversations for a user."""
    supabase = get_supabase()
    
    try:
        result = supabase.table("conversations").select("*").eq("user_id", user_id).order("updated_at", desc=True).limit(limit).execute()
        conversations = result.data or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch conversations: {str(e)}")
    
    # Get message counts and previews
    summaries = []
    for conv in conversations:
        conv_id = conv["id"]
        try:
            msgs_result = supabase.table("messages").select("*").eq("conversation_id", conv_id).order("created_at", desc=True).limit(2).execute()
            msgs = msgs_result.data or []
            msg_count = len(msgs)
            preview = msgs[-1]["content"][:50] + "..." if msgs else ""
        except Exception:
            msg_count = 0
            preview = ""
        
        summaries.append(ConversationSummary(
            id=conv_id,
            title=conv.get("title"),
            round_id=conv.get("round_id"),
            message_count=msg_count,
            last_message_at=conv.get("updated_at"),
            preview=preview,
        ))
    
    return {"conversations": summaries}


@app.get("/api/v1/coach/conversations/{conversation_id}/messages")
def get_conversation_messages(conversation_id: int, user_id: str):
    """Get messages for a conversation."""
    supabase = get_supabase()
    
    # Verify conversation belongs to user
    try:
        conv_result = supabase.table("conversations").select("*").eq("id", conversation_id).eq("user_id", user_id).single().execute()
        if not conv_result.data:
            raise HTTPException(status_code=404, detail="Conversation not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify conversation: {str(e)}")
    
    try:
        result = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        messages = result.data or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch messages: {str(e)}")
    
    return {
        "conversation_id": conversation_id,
        "messages": [
            Message(
                role=m["role"],
                content=m["content"],
                created_at=m.get("created_at"),
            ) for m in messages
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# ROUND HISTORY ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/rounds")
def get_rounds(user_id: str, limit: int = 10):
    """
    Retrieve round history with stats for a player.
    """
    supabase = get_supabase()
    
    try:
        result = supabase.table("rounds").select("*, round_stats(*)").eq("user_id", user_id).order("round_date", desc=True).limit(limit).execute()
        rounds = result.data or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch rounds: {str(e)}")
    
    return {
        "user_id": user_id,
        "count": len(rounds),
        "rounds": rounds,
    }
