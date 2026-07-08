import Foundation
import Supabase

/// Submits a completed round to the backend. Mirrors CoachService: shared
/// singleton, same base URL, authenticated session for the bearer token and the
/// lowercased user_id (match_shots is case-sensitive — see API_CONTRACT).
final class RoundService {
    static let shared = RoundService()
    private let baseURL = "http://localhost:8000"

    /// Builds the payload (injecting user_id + totals) and POSTs to /api/v1/rounds.
    func submit(
        courseId: String,
        course: CoursePayload,
        teeBox: TeeBoxPayload?,
        handicapIndex: Double,
        roundDate: String,
        holes: [HolePayload]
    ) async throws -> RoundIngestResponse {
        let session = try await supabase.auth.session
        let userID = session.user.id.uuidString.lowercased()

        let totalScore = holes.reduce(0) { $0 + $1.score }
        let totalPutts = holes.reduce(0) { $0 + ($1.putts ?? 0) }

        let payload = RoundPayload(
            user_id: userID,
            round_date: roundDate,
            course: course,
            handicap_index: handicapIndex,
            course_id: courseId,
            tee_box: teeBox,
            hole_data: holes,
            total_score: totalScore,
            total_putts: totalPutts
        )

        let url = URL(string: "\(baseURL)/api/v1/rounds")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(session.accessToken)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8) ?? "unknown error"
            throw URLError(.badServerResponse, userInfo: [NSLocalizedDescriptionKey: body])
        }

        return try JSONDecoder().decode(RoundIngestResponse.self, from: data)
    }
}
