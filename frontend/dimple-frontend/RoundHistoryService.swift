import Foundation
import Supabase

/// Fetches round history. Mirrors the other services: shared singleton, same
/// base URL, authenticated session for the bearer token + lowercased user_id.
final class RoundHistoryService {
    static let shared = RoundHistoryService()
    private let baseURL = "http://localhost:8000"

    func fetchRounds(limit: Int = 50) async throws -> [RoundHistoryItem] {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()

        var components = URLComponents(string: "\(baseURL)/api/v1/rounds")!
        components.queryItems = [
            URLQueryItem(name: "user_id", value: userID),
            URLQueryItem(name: "limit", value: String(limit)),
        ]

        var request = URLRequest(url: components.url!)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }

        return try JSONDecoder().decode(RoundHistoryResponse.self, from: data).rounds
    }
}
