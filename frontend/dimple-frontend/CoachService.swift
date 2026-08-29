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
    case badResponse
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
        case .badResponse:
            return "The coach sent something we couldn't read. Tap retry."
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

    // MARK: Streaming send

    /// One event from `POST /api/v1/coach/chat/stream`.
    enum StreamEvent {
        case meta(conversationID: Int, confidence: Int)
        case delta(String)
        case insight(String)
        case drill(DrillRecommendation)
        case done(answer: String)
    }

    // `nonisolated` because the project builds with SWIFT_DEFAULT_ACTOR_ISOLATION
    // = MainActor, and these are decoded off the main actor while the stream runs.
    private nonisolated struct MetaPayload: Decodable { let conversation_id: Int; let confidence: Int }
    private nonisolated struct TextPayload: Decodable { let text: String }
    private nonisolated struct DonePayload: Decodable { let answer: String }
    private nonisolated struct ErrorPayload: Decodable { let detail: String }

    /// Streams a coach reply as it is written.
    ///
    /// This is the path that survives a slow answer. The buffered endpoint can't
    /// send a byte until the model has finished, and Cloudflare only gives the
    /// origin 100s to start responding — so a long reply came back to the app as
    /// a 524 and read to the player as "couldn't reach the coach". Here the
    /// first bytes arrive immediately and the clock never starts.
    func stream(
        message: String,
        conversationID: Int?,
        roundID: Int? = nil
    ) -> AsyncThrowingStream<StreamEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let session = try await supabase.auth.session
                    let userID = session.user.id.uuidString.lowercased()

                    let url = URL(string: "\(baseURL)/api/v1/coach/chat/stream")!
                    var request = URLRequest(url: url)
                    request.httpMethod = "POST"
                    // Generous, but no longer load-bearing: the stream starts in
                    // seconds, so this only guards against a truly dead socket.
                    request.timeoutInterval = 180
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
                    request.httpBody = try JSONEncoder().encode(
                        ChatRequest(user_id: userID, conversation_id: conversationID, message: message, round_id: roundID)
                    )

                    let (bytes, response) = try await URLSession.shared.bytes(for: request)
                    guard let http = response as? HTTPURLResponse else {
                        throw CoachError.underlying("Unexpected response from the server.")
                    }
                    guard http.statusCode == 200 else {
                        throw CoachError.server(status: http.statusCode)
                    }

                    let decoder = JSONDecoder()
                    var eventName = "message"
                    var dataLines: [String] = []

                    // Server-Sent Events: `event:` names it, `data:` carries it,
                    // a blank line dispatches it, and a leading `:` is a keepalive.
                    func dispatch() throws {
                        defer { eventName = "message"; dataLines.removeAll() }
                        guard !dataLines.isEmpty else { return }
                        let data = Data(dataLines.joined(separator: "\n").utf8)
                        switch eventName {
                        case "meta":
                            let m = try decoder.decode(MetaPayload.self, from: data)
                            continuation.yield(.meta(conversationID: m.conversation_id, confidence: m.confidence))
                        case "delta":
                            continuation.yield(.delta(try decoder.decode(TextPayload.self, from: data).text))
                        case "insight":
                            continuation.yield(.insight(try decoder.decode(TextPayload.self, from: data).text))
                        case "drill":
                            continuation.yield(.drill(try decoder.decode(DrillRecommendation.self, from: data)))
                        case "done":
                            continuation.yield(.done(answer: try decoder.decode(DonePayload.self, from: data).answer))
                        case "error":
                            throw CoachError.underlying(try decoder.decode(ErrorPayload.self, from: data).detail)
                        default:
                            break // Unknown event type — ignore it rather than fail.
                        }
                    }

                    for try await line in bytes.lines {
                        if line.isEmpty {
                            try dispatch()
                        } else if line.hasPrefix(":") {
                            continue // keepalive
                        } else if line.hasPrefix("event:") {
                            eventName = String(line.dropFirst(6)).trimmingCharacters(in: .whitespaces)
                        } else if line.hasPrefix("data:") {
                            var value = String(line.dropFirst(5))
                            if value.hasPrefix(" ") { value.removeFirst() }
                            dataLines.append(value)
                        }
                    }
                    try dispatch() // in case the stream ended without a trailing blank line
                    continuation.finish()
                } catch let error as CoachError {
                    continuation.finish(throwing: error)
                } catch let error as URLError {
                    continuation.finish(throwing: CoachError(urlError: error))
                } catch is DecodingError {
                    continuation.finish(throwing: CoachError.badResponse)
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
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
