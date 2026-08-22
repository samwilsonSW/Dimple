import Foundation
import Supabase

/// User-facing coach failures. Maps low-level `URLError`s and non-200 responses
/// onto short, reassuring copy with a clear next step (retry) — so the chat never
/// surfaces a raw string like "Network connection was lost" (spec:
/// FRONTEND_LOADING_INDICATOR_SPEC.md). The chat error bubble renders
/// `errorDescription`.
enum CoachError: LocalizedError {
    case timedOut
    case connectionLost
    case offline
    case server(status: Int)
    case cancelled
    case underlying(String)

    init(urlError e: URLError) {
        switch e.code {
        case .timedOut:                            self = .timedOut
        case .networkConnectionLost:               self = .connectionLost
        case .notConnectedToInternet, .dataNotAllowed: self = .offline
        case .cancelled:                           self = .cancelled
        default:                                   self = .underlying(e.localizedDescription)
        }
    }

    var errorDescription: String? {
        switch self {
        case .timedOut:
            return "The coach is taking longer than usual. Tap retry to keep going."
        case .connectionLost:
            return "The connection dropped — this can happen when your phone goes to sleep. Tap retry."
        case .offline:
            return "You appear to be offline. Check your connection, then retry."
        case .server(let status):
            return status >= 500
                ? "The coach hit a snag on our end. Give it another try."
                : "Something went wrong (\(status)). Tap retry."
        case .cancelled:
            return "That request was cancelled. Tap retry."
        case .underlying(let message):
            return message
        }
    }
}

/// Conversational AI Coach client. Mirrors the other services: shared singleton,
/// same base URL, authenticated session for the bearer token + lowercased user_id.
///
/// Backed by `/api/v1/coach/chat` (replaces the old single-shot `/coach/ask`).
final class CoachService {
    static let shared = CoachService()
    private let baseURL = "https://dimple-api.chokepointmonitor.com"

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

        let data = try await Self.perform(request)
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

        let data = try await Self.perform(request)
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

        let data = try await Self.perform(request)
        return try JSONDecoder()
            .decode(ConversationMessagesResponse.self, from: data)
            .messages
            .map(\.chatMessage)
    }

    // MARK: Helpers

    /// Runs the request and normalises every failure into a `CoachError` so the
    /// UI can show reassuring copy. Transport failures (timeout, connection lost,
    /// offline) come from `URLSession`; non-200s become `.server(status:)`.
    private static func perform(_ request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw CoachError.underlying("Unexpected response from the server.")
            }
            guard http.statusCode == 200 else {
                #if DEBUG
                let body = String(data: data, encoding: .utf8) ?? "<no body>"
                print("CoachService HTTP \(http.statusCode): \(body)")
                #endif
                throw CoachError.server(status: http.statusCode)
            }
            return data
        } catch let error as CoachError {
            throw error
        } catch let error as URLError {
            throw CoachError(urlError: error)
        }
    }
}
