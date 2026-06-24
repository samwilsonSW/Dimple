import Foundation
import Supabase

/// Talks to the course endpoints. Mirrors `CoachService`: shared singleton,
/// same base URL, and an authenticated session for the bearer token.
class CourseService {
    static let shared = CourseService()
    private let baseURL = "http://localhost:8000"

    /// `GET /api/v1/courses/search?q={query}&limit={limit}`
    func search(query: String, limit: Int = 10) async throws -> [Course] {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        // Backend requires q >= 2 chars; skip the round trip otherwise.
        guard trimmed.count >= 2 else { return [] }

        var components = URLComponents(string: "\(baseURL)/api/v1/courses/search")!
        components.queryItems = [
            URLQueryItem(name: "q", value: trimmed),
            URLQueryItem(name: "limit", value: String(limit)),
        ]

        let response: CourseSearchResponse = try await get(url: components.url!)
        return response.courses
    }

    /// `GET /api/v1/courses/{course_id}`
    func details(courseId: String) async throws -> CourseDetail {
        let url = URL(string: "\(baseURL)/api/v1/courses/\(courseId)")!
        let response: CourseDetailResponse = try await get(url: url)
        return response.course
    }

    // MARK: - Private

    private func get<T: Decodable>(url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Attach the bearer token when signed in, matching CoachService.
        if let session = try? await supabase.auth.session {
            request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}
