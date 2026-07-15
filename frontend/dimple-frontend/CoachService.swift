import Foundation
import Supabase

/// Conversational AI Coach client. Mirrors the other services: shared singleton,
/// same base URL, authenticated session for the bearer token + lowercased user_id.
///
/// Backed by `/api/v1/coach/chat` (replaces the old single-shot `/coach/ask`).
final class CoachService {
    static let shared = CoachService()
    private let baseURL = "https://evidence-dialogue-chronicle-officers.trycloudflare.com"

    private struct ChatRequest: Encodable {
        let user_id: String
        let conversation_id: Int?
        let message: String
        let round_id: Int?
    }

    // MARK: Send a message

    /// Sends a message to the coach. Pass `conversationID == nil` to start a new
    /// conversation (optionally linked to a `roundID`); the response carries the
    /// new `conversation_id` to thread subsequent turns.
    func send(
        message: String,
        conversationID: Int?,
        roundID: Int? = nil
    ) async throws -> CoachChatResponse {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()

        let url = URL(string: "\(baseURL)/api/v1/coach/chat")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        // The coach calls an LLM in thinking mode; a fresh reply already runs
        // ~25-30s and grows as conversation history is re-fed into the prompt.
        // The default 60s URLSession timeout is too tight — bump it so a slow-but-
        // successful reply isn't cut off client-side (API_CONTRACT flags this risk).
        request.timeoutInterval = 180
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(
            ChatRequest(user_id: userID, conversation_id: conversationID, message: message, round_id: roundID)
        )

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response, data)
        return try JSONDecoder().decode(CoachChatResponse.self, from: data)
    }

    // MARK: Conversation list

    func fetchConversations(limit: Int = 20) async throws -> [ConversationSummary] {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()

        var components = URLComponents(string: "\(baseURL)/api/v1/coach/conversations")!
        components.queryItems = [
            URLQueryItem(name: "user_id", value: userID),
            URLQueryItem(name: "limit", value: String(limit)),
        ]

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response, data)
        return try JSONDecoder().decode(ConversationsResponse.self, from: data).conversations
    }

    // MARK: Conversation messages

    /// Loads the full message history for a conversation. The backend requires the
    /// `user_id` query param here (it verifies ownership) — the API_CONTRACT doc
    /// omits it, but `main.py` enforces it.
    func fetchMessages(conversationID: Int) async throws -> [ChatMessage] {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()

        var components = URLComponents(
            string: "\(baseURL)/api/v1/coach/conversations/\(conversationID)/messages"
        )!
        components.queryItems = [URLQueryItem(name: "user_id", value: userID)]

        var request = URLRequest(url: components.url!)
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response, data)
        return try JSONDecoder()
            .decode(ConversationMessagesResponse.self, from: data)
            .messages
            .map(\.chatMessage)
    }

    // MARK: Helpers

    private static func validate(_ response: URLResponse, _ data: Data) throws {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }
    }
}
