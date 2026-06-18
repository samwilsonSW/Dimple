import Foundation
import Supabase

class CoachService {
    static let shared = CoachService()
    private let baseURL = "http://localhost:8001"

    private struct CoachRequest: Encodable {
        let question: String
    }

    func ask(question: String) async throws -> CoachResponse {
        let session = try await supabase.auth.session

        let url = URL(string: "\(baseURL)/api/v1/coach/ask")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(CoachRequest(question: question))

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }

        return try JSONDecoder().decode(CoachResponse.self, from: data)
    }
}
