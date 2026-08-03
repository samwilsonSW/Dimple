# Coach Rework Spec — Phase A (Backend) + Phase B (Frontend)

> **Status:** Ready for implementation
> **API Version:** 0.7.0 (post-implementation)
> **Updated:** 2026-07-14

---

## Overview

This spec replaces the existing coach endpoint with a **data-source-aware, conversational architecture**. It is split into two phases:

- **Phase A (Kanary):** Backend changes — data inventory, conditional prompt assembly, conversation persistence
- **Phase B (Claude Code):** Frontend changes — chat UI, conversation history, message threading

---

## Current Problems

1. **System prompt lies** — claims "historical shot data with Strokes Gained values" but scorecard users have none
2. **25+ HCP gate** — blocks LLM entirely, returns canned fundamentals regardless of actual stats
3. **Dead prompt sections** — "Relevant Shot History" and "SG Summary" always included, even when empty
4. **No conversation memory** — each query is isolated, can't follow threads
5. **RAG is orphaned** — `match_shots` returns nothing for scorecard-only users, but we still call it

---

## Phase A: Backend Changes (Kanary) ✅ COMPLETE

### 1. Data Inventory

Before building any prompt, query what actually exists:

```python
data_inventory = {
    "round_stats_count": count(round_stats where user_id = X),
    "shot_embeddings_count": count(shot_embeddings where user_id = X),
    "reflections_count": count(rounds where user_id = X and reflection is not null),
    "has_round_stats": round_stats_count > 0,
    "has_trends": round_stats_count >= 3,
    "has_shots": shot_embeddings_count > 0,
    "has_reflections": reflections_count > 0,
}
```

### 2. Conditional Context Assembly

Build prompt sections ONLY when data exists:

| Section | Condition | Data Source |
|---------|-----------|-------------|
| **Scorecard Summary** | `has_round_stats` | `round_stats` table (latest 3 rounds) |
| **Trends** | `has_trends` | `get_trend_summary()` from `scorecard_stats.py` |
| **Shot History** | `has_shots` | RAG from `shot_embeddings` |
| **SG Summary** | `has_shots` | Calculated from retrieved shots |
| **Reflections** | `has_reflections` | `rounds.reflection` |
| **Data Disclaimer** | always | Honest statement about what's available |

### 3. Conversational Flow

When data is thin (1-2 rounds), the coach asks one focused follow-up question, incorporates the answer, and gives actionable advice.

**Example:**
```
User: "How can I improve?"
Coach: "I can see you have 2 rounds logged. Your GIR is 22% and you're averaging 
        36 putts per round. To give you better advice: where do you feel like you 
        lose the most strokes? Off the tee, approach shots, short game, or putting?"

User: "Definitely putting. I three-putt a lot."
Coach: "That tracks — 36 putts per round is about 4 above average for your handicap. 
        Let's work on lag putting. Try the Ladder Drill..."
```

**Key principle:** The coach uses whatever data it has + the player's self-reported insights. It never says "I can't help you."

### 4. Confidence Scaling (Replaces 25+ Gate)

| Level | Condition | Tone |
|-------|-----------|------|
| 1 | 1-2 rounds | "Limited data, but here's what I see..." + ask follow-up |
| 2 | 3-5 rounds | "Early trends suggest..." + may ask follow-up |
| 3 | 5+ rounds, no shots | "Clear patterns in your scorecard data..." |
| 4 | With shot data | "Your data shows specific patterns in..." |
| 5 | Rich shot + trend data | "Strong evidence that..." |

**Handicap is used for baseline comparison, NOT for gating.**

### 5. Zero-Data Fallback

**Copy:** "I don't have any rounds from you yet, so I can't spot patterns in your data. But I can still help. Tell me: where do you feel like you lose the most strokes? Off the tee, approach shots, short game, or putting? Or are you new to golf and looking for a place to start?"

**Branching:**
- Names a category → drill into that area + ask one clarifying question
- "I'm new" / "I don't know" → structured starter plan (grip, stance, 7-iron basics)

### 6. Files to Modify

| File | Changes |
|------|---------|
| `backend/app/main.py` | Replace `coach_ask` endpoint with new flow |
| `backend/app/models/round.py` | Add `DataInventory` model, update `CoachQuery`/`CoachResponse` |
| `backend/app/core/scorecard_stats.py` | Already has `get_trend_summary()` — wire it in |
| (optional) `backend/app/services/coach_prompt_builder.py` | Extract prompt assembly logic |

### 7. API Changes

**New endpoint (replaces `POST /api/v1/coach/ask`):**

```
POST /api/v1/coach/chat
```

**Request:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": 42,
  "message": "How can I work on my putting?",
  "round_id": 123
}
```

**Fields:**
- `conversation_id`: optional. If omitted, create new conversation.
- `round_id`: optional. Links conversation to a specific round.
- `message`: the user's message.

**Response:**
```json
{
  "conversation_id": 42,
  "message": {
    "role": "assistant",
    "content": "Based on your round stats...",
    "created_at": "2026-07-14T14:30:00Z"
  },
  "answer": "Your putting...",
  "confidence": 4,
  "key_insights": [...],
  "drill_recommendations": [...]
}
```

**New endpoints:**

```
GET /api/v1/coach/conversations?user_id={uuid}&limit=10
GET /api/v1/coach/conversations/{id}/messages
```

### 8. Database Migration

**Migration 016:**

```sql
CREATE TABLE conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    round_id BIGINT REFERENCES rounds(id) ON DELETE SET NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_conversations_user ON conversations(user_id, updated_at DESC);
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at ASC);
```

### 9. Design Decisions

1. **Skip RAG when `has_shots` is false** — saves compute and latency
2. **Use `get_trend_summary()`** — provides GIR%, Fairway%, Putts, SG trends over last 5 rounds
3. **Last N rounds, not time-based** — golfers play at different frequencies
4. **Shot data dominates, but recency matters** — yesterday's scorecard > year-old shot data
5. **No caching** — three count queries (~20ms) is negligible vs LLM latency

---

## Phase B: Frontend Changes (Claude Code) 🔄 NOT STARTED

### 1. New Views

**`CoachChatView`** — Main chat interface

```
┌─────────────────────────────────────┐
│  ← Back    Dimple Coach             │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ How'd I play today?         │    │ ← user bubble
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Your putting cost you 2.3   │    │ ← coach bubble
│  │ strokes. GIR was only 28%.  │    │
│  │                             │    │
│  │ [Drill: Ladder Drill]       │    │
│  └─────────────────────────────┘    │
│                                     │
│  [Type a message...          ] [Send]
└─────────────────────────────────────┘
```

**Features:**
- Bubble-style chat (user right, coach left)
- Drill recommendations as tappable cards within coach bubbles
- Scroll to bottom on new message
- Loading indicator while coach responds
- Error state with retry

**`ConversationListView`** — List of past conversations

```
┌─────────────────────────────────────┐
│  ← Back    Coach History            │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Round at Rawls — Jul 8      │    │
│  │ How'd I play? → 8 messages  │    │
│  └─────────────────────────────┘    │
│                                     │
│         [ + New Chat ]              │
└─────────────────────────────────────┘
```

### 2. Entry Points

| From | How |
|------|-----|
| **Round History** | Tap "Ask Coach" on a round card → starts conversation linked to that round |
| **Tab bar** | "Coach" tab → shows ConversationListView |
| **Scorecard submit** | After round submit, "Chat with Coach about this round" button |

### 3. Data Flow

1. User sends message → `POST /api/v1/coach/chat`
2. Show loading indicator
3. Receive response → append to chat
4. Save locally (no need to re-fetch history)

### 4. API Integration

- Replace calls to `POST /api/v1/coach/ask` with `POST /api/v1/coach/chat`
- Add `ConversationListView` using `GET /api/v1/coach/conversations`
- Add message history using `GET /api/v1/coach/conversations/{id}/messages`
- Handle `conversation_id` for multi-turn conversations

### 5. Acceptance Criteria

- [ ] User can start a new conversation from Round History or Coach tab
- [ ] Coach remembers context across multiple messages
- [ ] Round stats available throughout conversation
- [ ] Conversation history persisted and viewable
- [ ] Drill recommendations shown in chat bubbles
- [ ] Works with scorecard-only data (no shots needed)
- [ ] Loading and error states handled
- [ ] Accessible (VoiceOver reads message bubbles)

---

## Known Issues / Monitoring

### Confidence Score Debate
**Status:** Under observation  
**Context:** With 1 round, `determine_confidence()` returns 2 (data-richness based), but LLM returns 4 (signal-strength based). Duk prefers LLM's judgment — if the data is clear (e.g., -25.92 SG approach), confidence should reflect that clarity, not just data volume.  
**Decision:** Keep LLM confidence for now. Monitor if users find it misleading.  
**Revisit if:** Users with 1 round get overconfident advice that doesn't match reality.

---

## Success Criteria

- [x] 25+ HCP gate removed
- [x] Scorecard-only users get stats-based coaching (not generic fundamentals)
- [x] Prompt sections only appear when data exists
- [x] System prompt honestly describes available data
- [x] Confidence reflects signal strength (LLM judgment), not just data volume
- [x] RAG skipped when no shot data exists (save compute)
- [x] Coach asks follow-up questions when data is thin
- [x] Coach incorporates player self-reported insights into advice
- [x] Conversation history persisted in database
- [ ] Frontend chat UI supports multi-turn conversations (Phase B)

---

## Out of Scope

- Synthetic shot narratives from scorecard data
- Redesigning RAG for scorecard-derived pseudo-shots
- Multi-round trend visualization
- Personalized baseline adjustments
- Enhanced scorecard fields (miss direction for fairway/GIR)

---

*Phase A: Kanary implements backend changes*
*Phase B: Claude Code implements frontend changes*
*Both phases against this single spec*
