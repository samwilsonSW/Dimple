# Coach Rework Spec — Phase B: Data-Source-Aware Prompt Architecture

> **Status:** Draft v1 — for discussion, not final
> **Goal:** Make the coach honest about what data it has and coach from that reality

---

## Current Problems

1. **System prompt lies** — claims "historical shot data with Strokes Gained values" but scorecard users have none
2. **25+ HCP gate** — blocks LLM entirely, returns canned fundamentals regardless of actual stats
3. **Dead prompt sections** — "Relevant Shot History" and "SG Summary" always included, even when empty
4. **No data inventory** — coach doesn't know what it has vs what it lacks
5. **RAG is orphaned** — `match_shots` returns nothing for scorecard-only users, but we still call it

---

## New Architecture

### 1. Data Inventory (New Step)

Before building the prompt, query what actually exists:

```python
# Pseudocode
data_inventory = {
    "round_stats_count": count(round_stats where user_id = X),
    "shot_embeddings_count": count(shot_embeddings where user_id = X),
    "reflections_count": count(rounds where user_id = X and reflection is not null),
    "has_trends": round_stats_count >= 3,  # enough for trend analysis
    "has_shots": shot_embeddings_count > 0,
    "has_reflections": reflections_count > 0,
}
```

### 2. Conditional Context Assembly

Build prompt sections ONLY when data exists:

| Section | Condition | Data Source |
|---------|-----------|-------------|
| **Scorecard Summary** | `round_stats_count > 0` | `round_stats` table (latest 3 rounds) |
| **Trends** | `has_trends` | Aggregated `round_stats` (last 5-10 rounds) |
| **Shot History** | `has_shots` | RAG from `shot_embeddings` |
| **SG Summary** | `has_shots` | Calculated from retrieved shots |
| **Reflections** | `has_reflections` | `rounds.reflection` |
| **Data Disclaimer** | always | Honest statement about what's available |

### 3. Adaptive System Prompt

Template with conditional sections:

```
You are Dimple Coach, an expert golf coach.

{{data_disclaimer}}

{{shot_data_context}}

Be direct, data-driven, and actionable. Ground every insight in the provided context.
If you don't have enough data, say so and suggest what to track.
```

Where:
- `data_disclaimer` = "This player has N rounds of scorecard data (scores, GIR, fairways, putts)" + optionally "and M shots with detailed tracking"
- `shot_data_context` = only included if `has_shots` is true

### 4. Confidence Scaling (Replaces 25+ Gate)

Confidence (1-5) based on data richness, not handicap:

| Level | Condition | Tone |
|-------|-----------|------|
| 1 | 1-2 rounds | "Limited data, but here's what I see..." |
| 2 | 3-5 rounds | "Early trends suggest..." |
| 3 | 5+ rounds, no shots | "Clear patterns in your scorecard data..." |
| 4 | With shot data | "Your data shows specific patterns in..." |
| 5 | Rich shot + trend data | "Strong evidence that..." |

**Handicap is used for baseline comparison, NOT for gating.**

### 5. Prompt Structure (Final Assembly)

```
[SYSTEM]
You are Dimple Coach...
{{data_disclaimer}}
{{shot_data_context}}

[USER]
Player Question: {{question}}

{{scorecard_section}}

{{trend_section}}

{{sg_section}}

{{shot_history_section}}

{{reflection_section}}

{{instruction}}
```

Where each `{{section}}` is either populated or omitted based on inventory.

---

## Implementation Plan

### Files to Modify

| File | Changes |
|------|---------|
| `main.py` | Replace coach_ask endpoint with new flow |
| `models/round.py` | Add `DataInventory` model (internal) |
| (optional) New service | `coach_prompt_builder.py` — encapsulate prompt assembly |

### Pseudocode for New `coach_ask`

```python
@app.post("/api/v1/coach/ask", response_model=CoachResponse)
def coach_ask(query: CoachQuery):
    supabase = get_supabase()
    
    # 1. INVENTORY
    inventory = build_data_inventory(supabase, query.user_id)
    
    # 2. FETCH DATA (conditional)
    round_stats = fetch_round_stats(supabase, query.user_id) if inventory["has_round_stats"] else []
    similar_shots = fetch_similar_shots(supabase, query.user_id, query.question) if inventory["has_shots"] else []
    reflections = fetch_reflections(supabase, query.user_id) if inventory["has_reflections"] else []
    
    # 3. BUILD PROMPT
    system_prompt = build_system_prompt(inventory)
    user_prompt = build_user_prompt(
        question=query.question,
        round_stats=round_stats,
        similar_shots=similar_shots,
        reflections=reflections,
        inventory=inventory,
    )
    
    # 4. CALL LLM
    structured = generate_structured_coach_response(system_prompt, user_prompt)
    
    # 5. RETURN
    return CoachResponse(...)
```

---

## Open Questions (For Discussion)

1. **Should we skip RAG entirely when `has_shots` is false?** Currently we still embed the question and call `match_shots` — waste of compute?

2. **Trend calculation:** Should we add a `get_trend_summary()` call from `scorecard_stats.py`? It exists but isn't used in coach.

3. **Data freshness:** Should we weight recent rounds more heavily? Currently fetches "latest 5" with no time decay.

4. **Fallback when NO data:** What should the coach say if a brand new user with 0 rounds asks a question?

5. **Shot data vs scorecard data priority:** If a user has BOTH, which dominates? Or do we blend?

6. **Should we cache the inventory?** It's 3 count queries per coach request — cheap, but adds up.

---

## Success Criteria

- [ ] 25+ HCP gate removed
- [ ] Scorecard-only users get stats-based coaching (not generic fundamentals)
- [ ] Prompt sections only appear when data exists
- [ ] System prompt honestly describes available data
- [ ] Confidence reflects data richness, not handicap
- [ ] RAG skipped when no shot data exists (save compute)

---

## Out of Scope (Phase C)

- Synthetic shot narratives from scorecard data
- Redesigning RAG for scorecard-derived pseudo-shots
- Multi-round trend visualization
- Personalized baseline adjustments

---

*Drafted: 2026-07-14*
*Next: Review with Duk, iterate, then implement*
