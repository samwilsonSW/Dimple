import Foundation
import Supabase

class CoachService {
    static let shared = CoachService()
    private let baseURL = "http://localhost:8000"

    private struct CoachRequest: Encodable {
        let user_id: String
        let question: String
    }

    func ask(question: String) async throws -> CoachResponse {
        let session = try await supabase.auth.session

        // Use the authenticated player's real UUID. Lowercased because Swift's
        // UUID.uuidString is uppercase, but Supabase stores UUIDs lowercase and
        // match_shots filters on exact equality — uppercase would retrieve 0 shots.
        let userID = session.user.id.uuidString.lowercased()

        let url = URL(string: "\(baseURL)/api/v1/coach/ask")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(CoachRequest(user_id: userID, question: question))

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }

        return try JSONDecoder().decode(CoachResponse.self, from: data)
    }
}
