import Foundation

struct DrillRecommendation: Decodable, Identifiable, Equatable {
    var id: Int { priority }
    var priority: Int
    var focus_area: String
    var drill_name: String
    /// Drill steps in order. The coach streams these one `@step` at a time, so a
    /// card can paint its header before the steps have all arrived.
    var steps: [String]
    /// `steps` joined into one string. Kept so a client built against the old
    /// shape still renders something; prefer `steps`.
    var instructions: String
    var expected_outcome: String

    /// Every field is optional on the wire. A drill arriving half-built is the
    /// normal case while streaming, and a missing key must never throw away the
    /// whole message — the point of dropping JSON was to stop losing replies.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        priority = try c.decodeIfPresent(Int.self, forKey: .priority) ?? 1
        focus_area = try c.decodeIfPresent(String.self, forKey: .focus_area) ?? ""
        drill_name = try c.decodeIfPresent(String.self, forKey: .drill_name) ?? ""
        steps = try c.decodeIfPresent([String].self, forKey: .steps) ?? []
        expected_outcome = try c.decodeIfPresent(String.self, forKey: .expected_outcome) ?? ""
        let joined = try c.decodeIfPresent(String.self, forKey: .instructions) ?? ""
        instructions = joined.isEmpty ? steps.joined(separator: " ") : joined
    }

    private enum CodingKeys: String, CodingKey {
        case priority, focus_area, drill_name, steps, instructions, expected_outcome
    }
}

struct CoachResponse: Decodable {
    let answer: String
    let confidence: Int
    let key_insights: [String]
    let drill_recommendations: [DrillRecommendation]
}
