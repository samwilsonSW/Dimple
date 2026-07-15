import Foundation

// MARK: - Conversational Coach models
//
// Shapes follow the LIVE backend (`/api/v1/coach/chat` + conversation endpoints),
// verified against `backend/app/models/round.py` and `backend/app/main.py`.
// `DrillRecommendation` is reused from Models.swift.

// MARK: Chat message (UI model)

/// A single message rendered in the chat. `user`/`assistant` come from the
/// backend; `.error` is a client-only placeholder used to surface a failed send
/// inline in the thread (with a Retry affordance).
struct ChatMessage: Identifiable, Equatable {
    enum Role: String { case user, assistant, error }

    let id = UUID()
    let role: Role
    var content: String

    // Structured extras — only present on freshly-received assistant replies.
    // Historical messages loaded from the server carry text only (the backend
    // persists role + content, not the structured drills/insights).
    var confidence: Int? = nil
    var insights: [String] = []
    var drills: [DrillRecommendation] = []

    static func == (lhs: ChatMessage, rhs: ChatMessage) -> Bool { lhs.id == rhs.id }
}

// MARK: Send response (`POST /api/v1/coach/chat`)

struct CoachChatResponse: Decodable {
    let conversation_id: Int
    let answer: String
    let confidence: Int
    let key_insights: [String]
    let drill_recommendations: [DrillRecommendation]

    /// Fold the structured payload into a renderable assistant message.
    var assistantMessage: ChatMessage {
        ChatMessage(
            role: .assistant,
            content: answer,
            confidence: confidence,
            insights: key_insights,
            drills: drill_recommendations
        )
    }
}

// MARK: Conversation list (`GET /api/v1/coach/conversations`)

struct ConversationsResponse: Decodable {
    let conversations: [ConversationSummary]
}

struct ConversationSummary: Decodable, Identifiable, Hashable {
    let id: Int
    let title: String?
    let round_id: Int?
    let message_count: Int
    let last_message_at: String?
    let preview: String?

    var displayTitle: String {
        if let t = title, !t.isEmpty { return t }
        return "Coach Chat"
    }

    /// "Today" / "Yesterday" / "Jul 8" from an ISO-8601 timestamp.
    var displayDate: String {
        guard let raw = last_message_at else { return "" }
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = iso.date(from: raw)
            ?? ISO8601DateFormatter().date(from: raw)
            ?? parseLoose(raw)
        guard let d = date else { return "" }

        let cal = Calendar.current
        if cal.isDateInToday(d) { return "Today" }
        if cal.isDateInYesterday(d) { return "Yesterday" }
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_US_POSIX")
        out.dateFormat = "MMM d"
        return out.string(from: d)
    }

    /// Postgres timestamps sometimes arrive without a `Z`/offset — parse those too.
    private func parseLoose(_ raw: String) -> Date? {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        for fmt in ["yyyy-MM-dd'T'HH:mm:ss.SSSSSS", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd HH:mm:ss"] {
            f.dateFormat = fmt
            if let d = f.date(from: raw) { return d }
        }
        return nil
    }
}

// MARK: Conversation messages (`GET /api/v1/coach/conversations/{id}/messages`)

struct ConversationMessagesResponse: Decodable {
    let conversation_id: Int
    let messages: [StoredMessage]
}

struct StoredMessage: Decodable {
    let role: String
    let content: String
    let created_at: String?

    /// Map a persisted message onto the UI model. Unknown roles fall back to
    /// `.assistant` so the thread never drops a message.
    var chatMessage: ChatMessage {
        ChatMessage(role: ChatMessage.Role(rawValue: role) ?? .assistant, content: content)
    }
}
