# Frontend Loading Indicator Spec — Coach Chat

> **Owner:** Claude Code  
> **Status:** Ready for implementation  
> **Branch:** Kanary (working branch)  
> **Depends on:** Backend PR `feature/coach-latency-fixes` (connection pooling + non-fatal verify)

---

## Problem

When a user sends a message to the coach, there is **zero visual feedback** while waiting for the backend response. The user sits staring at a static screen for 15–30 seconds with no indication that:
1. Their message was received
2. The coach is "thinking"
3. Anything is happening at all

If the phone goes to sleep during this wait, reopening the app shows "Network connection was lost" — compounding the frustration.

---

## Goal

Make the waiting experience **feel intentional and responsive**, not broken. Three principles:
1. **Immediate acknowledgment** — user message appears instantly in the chat
2. **Clear "thinking" state** — coach is visibly processing
3. **Graceful degradation** — if the phone sleeps or connection drops, the UI recovers without scary errors

---

## Acceptance Criteria

- [ ] User message appears in chat bubble **immediately** upon send (optimistic UI)
- [ ] Coach shows a "typing/thinking" indicator while waiting for response
- [ ] If request fails (timeout, sleep, network drop), show **retry UI** — not a generic error
- [ ] If user backgrounds the app and returns, chat state is preserved (no re-fetch needed)
- [ ] Works with existing `CoachChatView` + `CoachService` architecture

---

## Implementation Plan

### 1. Optimistic Message Insertion

**Current behavior:** `CoachChatView` waits for `CoachService.send()` to return before showing anything.

**New behavior:**
```swift
// In CoachChatView.sendMessage()
// 1. Immediately append user message to local messages array
let optimisticMessage = ChatMessage(role: .user, content: text, isLocal: true)
messages.append(optimisticMessage)
scrollToBottom()

// 2. Show coach "thinking" indicator
isCoachTyping = true

// 3. Fire request async
Task {
    do {
        let response = try await CoachService.send(message: text, conversationId: conversationId)
        // 4. Replace optimistic with server-confirmed (or just append coach response)
        await MainActor.run {
            isCoachTyping = false
            messages.append(ChatMessage(role: .assistant, content: response.answer, ...))
        }
    } catch {
        await MainActor.run {
            isCoachTyping = false
            // 5. Show retry state on the optimistic message or as a system bubble
            showRetryForMessage(optimisticMessage)
        }
    }
}
```

**Model change:**
```swift
struct ChatMessage: Identifiable {
    let id = UUID()
    let role: MessageRole
    let content: String
    let createdAt: Date?
    let isLocal: Bool  // NEW: true = optimistic, not yet confirmed by server
    let failed: Bool   // NEW: true = send failed, show retry
}
```

### 2. Coach Typing Indicator

**Visual:** Animated "…" dots inside a left-aligned coach bubble (same style as existing coach messages but with pulsing opacity).

```swift
struct CoachTypingIndicator: View {
    @State private var dotCount = 0
    
    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { i in
                Circle()
                    .fill(Color.secondary.opacity(i < dotCount ? 1.0 : 0.3))
                    .frame(width: 6, height: 6)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(Color(.systemGray6))
        .cornerRadius(16)
        .onAppear { startAnimation() }
    }
    
    func startAnimation() {
        Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { _ in
            dotCount = (dotCount + 1) % 4
        }
    }
}
```

**Placement:** Insert as a temporary message in the `messages` array when `isCoachTyping = true`. Remove when response arrives.

### 3. Retry UI ( replaces "Network connection was lost" )

**Current behavior:** Generic error banner or alert.

**New behavior:** Inline retry on the failed message bubble.

```swift
struct ChatMessageBubble: View {
    let message: ChatMessage
    let onRetry: () -> Void
    
    var body: some View {
        HStack {
            if message.role == .user { Spacer() }
            
            VStack(alignment: message.role == .user ? .trailing : .leading) {
                Text(message.content)
                    .padding(12)
                    .background(message.role == .user ? Color.accentColor : Color(.systemGray6))
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(16)
                
                if message.failed {
                    Button(action: onRetry) {
                        Label("Retry", systemImage: "arrow.clockwise")
                            .font(.caption)
                    }
                    .padding(.top, 4)
                }
            }
            
            if message.role == .assistant { Spacer() }
        }
    }
}
```

**Error handling in `CoachService`:**
- Distinguish `URLError.networkConnectionLost` (phone slept) from other errors
- For connection-lost: show retry, don't clear optimistic message
- For timeout: show "Coach is taking longer than usual…" + retry
- For 500: show "Coach had a hiccup. Try again?" + retry

### 4. State Preservation on Background

**Current behavior:** App returns to chat, re-fetches conversation from scratch (or shows stale state).

**New behavior:**
- `CoachChatViewModel` holds `messages` array in memory
- When app enters background, **do nothing** — `messages` persists in `@StateObject`
- When app returns to foreground, **check if a request is in-flight**:
  - If `isCoachTyping == true` but no active `Task`, the request died in background
  - Auto-retry the last user message (or show retry UI)

```swift
@main
struct DimpleApp: App {
    @Environment(\.scenePhase) var scenePhase
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .onChange(of: scenePhase) { newPhase in
            if newPhase == .active {
                NotificationCenter.default.post(name: .appReturnedToForeground, object: nil)
            }
        }
    }
}

// In CoachChatViewModel
init() {
    NotificationCenter.default.addObserver(
        self,
        selector: #selector(handleForeground),
        name: .appReturnedToForeground,
        object: nil
    )
}

@objc func handleForeground() {
    if isCoachTyping && !hasActiveRequest {
        // Request died in background — show retry
        markLastMessageAsFailed()
    }
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `CoachChatView.swift` | Optimistic insertion, typing indicator, retry UI |
| `CoachChatViewModel.swift` (or inline `@State` in view) | Track `isCoachTyping`, `hasActiveRequest`, handle foreground |
| `CoachService.swift` | Better error classification (connection-lost vs timeout vs 500) |
| `ChatMessage.swift` (or model in view) | Add `isLocal`, `failed` fields |

---

## Open Questions for Duk (Taste)

1. **Typing indicator style:** Pulsing dots (proposed) or "Coach is thinking…" text?
2. **Retry placement:** Inline on the message bubble (proposed) or a bottom banner?
3. **Auto-retry on foreground:** Should we automatically retry, or always ask? (Auto-retry feels magic but could be annoying if it fails again)

---

## Success Criteria

- [ ] User sends message → sees it instantly → sees coach typing → gets response
- [ ] Phone sleeps mid-request → reopen app → sees retry option (not "Network connection was lost")
- [ ] Build green (`xcodebuild`)
- [ ] Works on device (Duk test)

---

*Spec by Kanary. Implementation by Claude Code. Taste by Duk.*
