import Foundation

// MARK: - Round History response
//
// Shapes follow the LIVE backend (`GET /api/v1/rounds`), verified against the
// running server — which differs from the spec in two ways:
//   • `id` is an Int (BIGSERIAL), not a UUID.
//   • `round_stats` comes back as an ARRAY (PostgREST embed), not an object.
// The item decoder tolerates array, single-object, or null for `round_stats`.

struct RoundHistoryResponse: Decodable {
    let count: Int
    let rounds: [RoundHistoryItem]
}

struct RoundCourse: Decodable, Hashable {
    let name: String?
    let city: String?
    let state: String?

    var displayName: String {
        if let n = name, !n.isEmpty { return n }
        return "Unknown Course"
    }
    var location: String {
        [city, state].compactMap { $0?.isEmpty == false ? $0 : nil }.joined(separator: ", ")
    }
}

struct RoundHistoryItem: Decodable, Identifiable {
    let id: Int
    let roundDate: String
    let course: RoundCourse
    let handicapIndex: Double?
    let reflection: String?
    let stats: RoundStats?

    private enum CodingKeys: String, CodingKey {
        case id, course, reflection
        case roundDate = "round_date"
        case handicapIndex = "handicap_index"
        case roundStats = "round_stats"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        roundDate = try c.decodeIfPresent(String.self, forKey: .roundDate) ?? ""
        course = try c.decodeIfPresent(RoundCourse.self, forKey: .course)
            ?? RoundCourse(name: nil, city: nil, state: nil)
        handicapIndex = try c.decodeIfPresent(Double.self, forKey: .handicapIndex)
        reflection = try c.decodeIfPresent(String.self, forKey: .reflection)

        // PostgREST embeds the joined stats as an array; tolerate object/null too.
        if let arr = try? c.decode([RoundStats].self, forKey: .roundStats) {
            stats = arr.first
        } else if let obj = try? c.decode(RoundStats.self, forKey: .roundStats) {
            stats = obj
        } else {
            stats = nil
        }
    }
}

// Identity-based equality so the item can drive navigation without RoundStats
// needing to be Hashable.
extension RoundHistoryItem: Hashable {
    static func == (lhs: RoundHistoryItem, rhs: RoundHistoryItem) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }
}

// MARK: - Display helpers

extension RoundHistoryItem {
    var hasStats: Bool { stats != nil }

    var totalScore: Int? { stats?.total_score }

    /// `strokes_over_under` rounded to a whole number.
    var vsPar: Int? { stats?.strokes_over_under.map { Int($0.rounded()) } }

    /// Course par = total score − (over/under par).
    var par: Int? {
        guard let s = totalScore, let v = vsPar else { return nil }
        return s - v
    }

    var scoreText: String { totalScore.map { "\($0)" } ?? "–" }
    var parText: String? { par.map { "(\($0))" } }
    var vsParText: String? { vsPar.map { formatToPar($0) } }
    var girText: String? { stats?.gir_count.map { "\($0) GIR" } }

    /// "Today" / "Yesterday" / weekday (if <7 days) / "Jun 24".
    var displayDate: String {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.dateFormat = "yyyy-MM-dd"
        guard let d = parser.date(from: roundDate) else { return roundDate }

        let cal = Calendar.current
        if cal.isDateInToday(d) { return "Today" }
        if cal.isDateInYesterday(d) { return "Yesterday" }
        let days = cal.dateComponents([.day], from: cal.startOfDay(for: d), to: cal.startOfDay(for: Date())).day ?? 99
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_US_POSIX")
        out.dateFormat = (days > 1 && days < 7) ? "EEEE" : "MMM d"
        return out.string(from: d)
    }

    /// Spoken summary for VoiceOver.
    var accessibilityText: String {
        var parts = [course.displayName]
        if !course.location.isEmpty { parts.append(course.location) }
        parts.append(displayDate)
        if let s = totalScore { parts.append("score \(s)") }
        if let v = vsPar {
            parts.append(v == 0 ? "even par" : (v > 0 ? "\(v) over par" : "\(-v) under par"))
        }
        if let g = stats?.gir_count { parts.append("\(g) greens in regulation") }
        if !hasStats { parts.append("stats unavailable") }
        return parts.joined(separator: ", ")
    }
}
