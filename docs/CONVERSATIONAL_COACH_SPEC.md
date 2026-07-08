# Conversational Coach — Spec

> **Status:** Draft — ready for Duk review, then Claude Code build  
> **Owner:** Kanary (spec) → Duk (taste review) → Claude Code (frontend) → Kanary (backend)  
> **Priority:** P1 — post-Sunday test, pre shot-by-shot entry  
> **Updated:** 2026-07-08

---

## Problem

Right now the coach is a Q&A bot. You ask one question, get one answer, done. The real value of an AI coach is **back-and-forth** — drilling into specifics, following threads, building context over a conversation.

**Example of what we want:**

```
User: "How'd I play today?"
Coach: "Your putting cost you 2.3 strokes. GIR was only 28%."

User: "Yeah my putting was rough. What should I work on?"
Coach: "You had 34 putts. Based on your handicap, you should average 32. 
        The issue is likely lag putting — focus on speed control."

User: "Any drills for that?"
Coach: "Try the Ladder Drill..."
```

**Without conversation memory, each query is isolated.** The coach forgets it just told you putting was bad. It can't follow threads.

---

## Goals

1. **Multi-turn conversations** — User and coach go back and forth naturally
2. **Context preservation** — Coach remembers what was discussed in this conversation
3. **Round-linked or general** — Conversations can be tied to a specific round, or be general "ask anything"
4. **Stats-aware throughout** — Even in turn 3 of a conversation, coach still has access to round stats/trends
5. **Simple UI** — Chat interface, not a form

---

## Architecture

### New Database Tables

**`conversations`**
- `id` (BIGSERIAL, PK)
- `user_id` (text, lowercase UUID)
- `round_id` (BIGINT, FK → rounds, nullable) — link to a specific round, or null for general chat
- `title` (text, nullable) — auto-generated summary, e.g. "Round at Rawls — Jul 8"
- `created_at` (timestamp)
- `updated_at` (timestamp)

**`messages`**
- `id` (BIGSERIAL, PK)
- `conversation_id` (BIGINT, FK → conversations, ON DELETE CASCADE)
- `role` (text) — `"user"` or `"assistant"`
- `content` (text) — message text
- `created_at` (timestamp)

### API Changes

**New endpoint (replaces `/api/v1/coach/ask`):**

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

**Field rules:**
- `conversation_id`: optional. If omitted, create new conversation.
- `round_id`: optional. If provided, link conversation to this round (for round-specific context).
- `message`: the user's message.

**Response:**
```json
{
  "conversation_id": 42,
  "message": {
    "role": "assistant",
    "content": "Based on your round stats...",
    "created_at": "2026-07-08T14:30:00Z"
  },
  "answer": "Your putting...",
  "confidence": 4,
  "key_insights": [...],
  "drill_recommendations": [...]
}
```

**New endpoint for conversation history:**

```
GET /api/v1/coach/conversations?user_id={uuid}&limit=10
```

**Response:**
```json
{
  "conversations": [
    {
      "id": 42,
      "title": "Round at Rawls — Jul 8",
      "round_id": 123,
      "message_count": 8,
      "last_message_at": "2026-07-08T14:30:00Z",
      "preview": "How'd I play? → Your putting..."
    }
  ]
}
```

**New endpoint for messages in a conversation:**

```
GET /api/v1/coach/conversations/{id}/messages
```

**Response:**
```json
{
  "conversation_id": 42,
  "messages": [
    {"role": "user", "content": "How'd I play?", "created_at": "..."},
    {"role": "assistant", "content": "Your putting cost you...", "created_at": "..."},
    {"role": "user", "content": "How do I fix my putting?", "created_at": "..."},
    {"role": "assistant", "content": "Try the Ladder Drill...", "created_at": "..."}
  ]
}
```

---

## Backend Logic

### 1. Create or Continue Conversation

```python
if conversation_id provided:
    fetch conversation, verify user_id matches
else:
    create new conversation
    if round_id provided:
        link to round
        auto-generate title from round data (e.g. "Round at {course_name} — {date}")
```

### 2. Fetch Context

For every message, fetch:
- **Recent messages** from this conversation (last 10-20)
- **Round stats** (if round_id linked)
- **Recent round stats** (last 5 rounds for trends)
- **Vector search** on the *current question* only (not historical questions)

### 3. Build Prompt

```
System: You are Dimple Coach, an expert golf coach...

[Round stats context — same as current coach]

[Conversation history]
User: How'd I play?
Assistant: Your putting cost you 2.3 strokes...
User: How do I fix my putting?

[Retrieved shots for current question]

Now respond to: "How do I fix my putting?"
```

### 4. Save Message Pair

```python
# Save user message
insert into messages (conversation_id, role="user", content=message)

# Save assistant response
insert into messages (conversation_id, role="assistant", content=answer)

# Update conversation updated_at
```

### 5. Auto-Generate Title

On first message, generate a title using a quick LLM call or heuristic:
- If round-linked: "Round at {course} — {date}"
- If general: "Coach Chat — {date}"
- Or ask LLM: "Summarize this conversation in 5 words or less"

---

## Frontend (Claude Code)

### New Views

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
│  ┌─────────────────────────────┐    │
│  │ How do I fix my putting?    │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Focus on lag putting...     │    │
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
│  ┌─────────────────────────────┐    │
│  │ Coach Chat — Jul 5          │    │
│  │ How's my driving? → 4 msgs  │    │
│  └─────────────────────────────┘    │
│                                     │
│         [ + New Chat ]              │
└─────────────────────────────────────┘
```

### Entry Points

| From | How |
|------|-----|
| **Round History** | Tap "Ask Coach" on a round card → starts conversation linked to that round |
| **Tab bar** | "Coach" tab → shows ConversationListView |
| **Scorecard submit** | After round submit, "Chat with Coach about this round" button |

### Data Flow

1. User sends message → `POST /api/v1/coach/chat`
2. Show loading indicator
3. Receive response → append to chat
4. Save locally (no need to re-fetch history)

---

## Migration

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

---

## Open Questions for Duk

1. **Conversation limit?** How many messages per conversation? (suggest 50, then auto-archive)
2. **Conversation expiry?** Delete old conversations after N days? (suggest keep forever, limit list to last 20)
3. **Title generation?** Auto-generate from LLM, or use heuristic (round date/course)?
4. **Drill cards in chat?** Show drills as tappable cards within coach bubbles, or separate section?
5. **Round-linked vs general?** Should all conversations be round-linked, or allow general "how's my game?" chats?

---

## Acceptance Criteria

- [ ] User can start a new conversation from Round History or Coach tab
- [ ] Coach remembers context across multiple messages
- [ ] Round stats available throughout conversation
- [ ] Conversation history persisted and viewable
- [ ] Drill recommendations shown in chat bubbles
- [ ] Works with scorecard-only data (no shots needed)
- [ ] Loading and error states handled
- [ ] Accessible (VoiceOver reads message bubbles)

---

*Spec draft: 2026-07-08. Review with Duk, then hand to Claude Code.*
