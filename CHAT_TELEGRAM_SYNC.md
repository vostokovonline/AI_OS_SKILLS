# Chat & Telegram Sync - Implementation Summary

## Date: 2026-04-09

## Problems Found

| # | Problem | Severity |
|---|---------|----------|
| 1 | `POST /chat` always returned "Processing..." - actual response was lost | 🔴 CRITICAL |
| 2 | `POST /chat/sync` was **single-turn** - ignored session_id, no conversation history | 🔴 CRITICAL |
| 3 | Telegram `/chat` and Web Chat used different paths with different behavior | 🟡 MEDIUM |
| 4 | Messages were written to DB but never read back | 🟡 MEDIUM |
| 5 | LangGraph MemorySaver was in-memory only (lost on restart) | 🟡 MEDIUM |

## Changes Made

### 1. Backend: `/chat/sync` now supports persistent conversation history ✅

**File:** `services/core/main.py`

**Before:**
```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": req.content}
]
# Single turn, no history, no session_id usage
```

**After:**
```python
# 1. Load last 10 messages from DB for this session_id
recent_messages = load_from_db(session_id)

# 2. Build conversation context
messages = [system_prompt] + recent_messages + [user_message]

# 3. Save user message AND assistant response to DB
save_to_db(session_id, "user", req.content)
save_to_db(session_id, "assistant", response_text)

# 4. Return session_id to client for continuity
return {"status": "ok", "session_id": sid, "response": response_text}
```

### 2. Backend: New endpoints for chat history and session management ✅

**New endpoints:**
- `GET /chat/{session_id}/history?limit=20` — Get message history for a session
- `GET /chat/sessions?limit=20` — List recent chat sessions with preview

### 3. Telegram Bot: Now uses session_id for conversation context ✅

**File:** `services/telegram/telegram_bot.py`

**Before:**
```python
response = await client.post(
    f"{CORE_API_URL}/chat/sync",
    json={"content": user_message},
    timeout=30.0
)
# No session_id = no conversation history
```

**After:**
```python
# Get or create persistent session for this Telegram user
session_key = f"telegram:user_chat_session:{user_id}"
session_id = redis.get(session_key) or str(uuid.uuid4())
redis.set(session_key, session_id, ex=86400 * 30)  # 30 days

response = await client.post(
    f"{CORE_API_URL}/chat/sync",
    json={"session_id": session_id, "content": user_message},
    timeout=60.0  # Increased timeout for LLM response
)
```

**Result:** Each Telegram user now has a persistent chat session that survives bot restarts.

### 4. Web Chat (UnifiedChat): Now uses `/chat/sync` with session persistence ✅

**File:** `services/dashboard_v2/src/pages/UnifiedChat.tsx`

**Before:**
```typescript
const response = await apiClient.post('/chat', { message: input });
// /chat returns "Processing..." - response lost
```

**After:**
```typescript
const response = await fetch('/chat/sync', {
  method: 'POST',
  body: JSON.stringify({
    session_id: sessionId || undefined,  // Persistent session
    content: currentInput
  })
});

const data = await response.json();
// data.session_id saved to localStorage for continuity
```

**Features added:**
- Session ID stored in `localStorage` — survives page refresh
- On mount, loads last 50 messages from `/chat/{session_id}/history`
- Real responses instead of "Processing..."

## Architecture After Fix

```
┌──────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                        │
├─────────────────────────┬────────────────────────────────────┤
│    Web Chat (Dashboard) │    Telegram Bot                     │
│  - UnifiedChat.tsx      │  - /chat <message>                  │
│  - localStorage session │  - Redis session (30 days)          │
│  - Loads history on mount│  - Persistent per user             │
└────────────┬────────────┴─────────────┬──────────────────────┘
             │                          │
             │  POST /chat/sync         │  POST /chat/sync
             │  {session_id, content}   │  {session_id, content}
             ▼                          ▼
┌──────────────────────────────────────────────────────────────┐
│                     CORE API (/chat/sync)                     │
│                                                               │
│  1. Load last 10 messages from DB for session_id             │
│  2. Build messages: [system] + [history] + [user_message]    │
│  3. Call LLM via chat_with_fallback()                        │
│  4. Save user message + assistant response to DB             │
│  5. Return {status, session_id, response}                    │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    DATABASE (PostgreSQL)                      │
│                                                               │
│  ChatSession: id, created_at                                 │
│  Message: session_id, role, content, created_at              │
│                                                               │
│  ← Messages now WRITTEN and READ back                        │
└──────────────────────────────────────────────────────────────┘
```

## Key Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Web Chat response** | Always "Processing..." | Real LLM response |
| **Conversation context** | None (single-turn) | Last 10 messages from DB |
| **Session persistence** | In-memory only (lost on restart) | PostgreSQL (persistent) |
| **Telegram chat history** | None | Redis session_id + DB history |
| **Session continuity** | Lost on page refresh | localStorage (web) / Redis (telegram) |
| **History endpoint** | None | `GET /chat/{session_id}/history` |

## How to Test

### Web Chat
1. Open dashboard → "Чат с системой"
2. Send a message — should get real response
3. Refresh page — history should load automatically
4. Send follow-up message referencing previous context — should understand context

### Telegram
1. `/chat Привет, как дела?` — should get response
2. `/chat Что я спросил до этого?` — should remember previous message
3. Restart telegram bot — conversation context should persist

### API Direct Test
```bash
# Create session and send message
curl -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"content": "Привет! Как мои цели?"}'

# Response includes session_id
# {"status": "ok", "session_id": "...", "response": "..."}

# Continue conversation with same session_id
curl -X POST http://localhost:8000/chat/sync \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<from_previous>", "content": "А что дальше?"}'

# Get history
curl http://localhost:8000/chat/<session_id>/history?limit=10
```

## Files Modified

| File | Changes |
|------|---------|
| `services/core/main.py` | Enhanced `/chat/sync` with history, added `/chat/{session_id}/history` and `/chat/sessions` endpoints |
| `services/telegram/telegram_bot.py` | Added Redis session management for persistent chat context |
| `services/dashboard_v2/src/pages/UnifiedChat.tsx` | Switched to `/chat/sync`, added session persistence, history loading |
