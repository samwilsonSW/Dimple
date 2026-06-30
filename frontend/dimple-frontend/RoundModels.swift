import Foundation

// MARK: - Round Mode

enum RoundMode: String, Codable, CaseIterable, Identifiable {
    case full18
    case front9
    case back9
    case flexible

    var id: String { rawValue }

    var title: String {
        switch self {
        case .full18:   return "Full 18 Holes"
        case .front9:   return "Front 9 Only"
        case .back9:    return "Back 9 Only"
        case .flexible: return "Play Until Dark"
        }
    }

    var subtitle: String {
        switch self {
        case .full18:   return "All 18 holes"
        case .front9:   return "Holes 1–9"
        case .back9:    return "Holes 10–18"
        case .flexible: return "Submit whenever you stop"
        }
    }

    var systemImage: String {
        switch self {
        case .full18:   return "flag.2.crossed"
        case .front9:   return "flag"
        case .back9:    return "flag.checkered"
        case .flexible: return "sun.haze"
        }
    }

    /// Hole numbers this mode covers, given the course's hole template.
    func holeNumbers(in template: [HoleInfo]) -> [Int] {
        let all = template.map(\.holeNumber).sorted()
        switch self {
        case .full18, .flexible: return all
        case .front9:            return all.filter { $0 <= 9 }
        case .back9:             return all.filter { $0 >= 10 }
        }
    }

    /// Flexible mode lets the player submit at any point (e.g. sun went down).
    var allowsEarlySubmit: Bool { self == .flexible }
}

// MARK: - Scorecard Start (tee picker + setup → scorecard hand-off)

struct ScorecardStart: Hashable {
    let selection: RoundCourseSelection
    let mode: RoundMode
    let handicapIndex: Double
    let roundDate: String
}

/// Today's date as `YYYY-MM-DD` (round_date format per API_CONTRACT).
func isoDateToday() -> String {
    let f = DateFormatter()
    f.calendar = Calendar(identifier: .gregorian)
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    return f.string(from: Date())
}

/// Parses a `YYYY-MM-DD` string for display; falls back to the raw string.
func displayDate(_ iso: String) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.dateFormat = "yyyy-MM-dd"
    guard let d = f.date(from: iso) else { return iso }
    return d.formatted(date: .abbreviated, time: .omitted)
}

// MARK: - Local Hole Entry (draft + working state)

struct HoleEntry: Codable, Hashable {
    let holeNumber: Int
    let par: Int
    var yardage: Int?
    var score: Int
    var putts: Int?
    var fairway: Bool?   // nil = not recorded; always nil on par 3
    var gir: Bool?       // nil = not recorded
}

// MARK: - Draft (local persistence, survives crash / app kill)

struct DraftRound: Codable {
    let courseId: String
    let courseName: String
    let city: String?
    let state: String?
    let teeBox: TeeBox
    let holeTemplate: [HoleInfo]   // par/yardage for every hole — lets resume work offline
    let handicapIndex: Double
    let roundDate: String          // YYYY-MM-DD
    let mode: RoundMode
    var currentHoleNumber: Int
    var holes: [HoleEntry]         // only holes the player has entered
    var lastSaved: Date
}

// MARK: - Submit Payload (POST /api/v1/rounds)
//
// Optional fields with nil are omitted by JSONEncoder's synthesized encoding,
// which the backend treats as null (pydantic Optional). That matches the
// contract: e.g. omitted `fairway` on a par 3 reads as null server-side.

struct RoundPayload: Encodable {
    let user_id: String
    let round_date: String
    let course: CoursePayload
    let handicap_index: Double
    let course_id: String?
    let tee_box: TeeBoxPayload?
    let hole_data: [HolePayload]
    let total_score: Int
    let total_putts: Int
}

struct CoursePayload: Encodable {
    let name: String
    let city: String?
    let state: String?
}

struct TeeBoxPayload: Encodable {
    let tee_name: String
    let rating: Double?
    let slope: Int?
}

struct HolePayload: Encodable {
    let hole_number: Int
    let par: Int
    let yardage: Int?
    let score: Int
    let putts: Int?
    let fairway: Bool?
    let gir: Bool?
}

// MARK: - Submit Response

struct RoundIngestResponse: Decodable {
    let round_id: Int?     // backend returns the int rounds.id (BIGSERIAL), not a UUID string
    let status: String?
    let round_stats: RoundStats?
}

struct RoundStats: Decodable {
    let total_score: Int?
    let total_putts: Int?
    let gir_count: Int?
    let gir_percentage: Double?
    let fairways_hit: Int?
    let fairways_possible: Int?
    let fairway_percentage: Double?
    let sg_putting: Double?
    let sg_approach: Double?
    let strokes_over_under: Double?
    let avg_putts_per_hole: Double?
    let avg_score_to_par: Double?
}
