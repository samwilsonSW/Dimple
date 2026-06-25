import Foundation

// MARK: - Course Search
//
// Shapes follow the live backend (`GET /api/v1/courses/search`,
// `GET /api/v1/courses/{id}`). The backend currently returns `holes`, `tees`,
// and `holes` where API_CONTRACT.md documents `holes_count`, `tee_data`, and
// `hole_data`. Decoding accepts either spelling so the app keeps working
// whichever way the contract drift is resolved.

struct Course: Decodable, Identifiable, Hashable {
    let id: String
    let name: String
    let clubName: String?
    let city: String?
    let state: String?
    let country: String?
    let holesCount: Int?

    /// "Lubbock, TX" — omits whichever component is missing.
    var location: String {
        [city, state].compactMap { $0?.isEmpty == false ? $0 : nil }.joined(separator: ", ")
    }

    private enum CodingKeys: String, CodingKey {
        case id, name, city, state, country, holes
        case clubName = "club_name"
        case holesCount = "holes_count"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        clubName = try c.decodeIfPresent(String.self, forKey: .clubName)
        city = try c.decodeIfPresent(String.self, forKey: .city)
        state = try c.decodeIfPresent(String.self, forKey: .state)
        country = try c.decodeIfPresent(String.self, forKey: .country)
        holesCount = try c.decodeIfPresent(Int.self, forKey: .holes)
            ?? c.decodeIfPresent(Int.self, forKey: .holesCount)
    }
}

struct CourseSearchResponse: Decodable {
    let query: String
    let count: Int
    let courses: [Course]
}

// MARK: - Course Details

struct TeeBox: Codable, Identifiable, Hashable {
    let teeId: String
    let teeName: String
    let gender: String?
    let length: Int?
    let par: Int?
    let slope: Int?
    let rating: Double?

    var id: String { teeId }

    private enum CodingKeys: String, CodingKey {
        case gender, length, par, slope, rating
        case teeId = "tee_id"
        case teeName = "tee_name"
    }
}

struct HoleInfo: Codable, Identifiable, Hashable {
    let holeNumber: Int
    let par: Int
    let yardage: Int?
    let handicap: Int?

    var id: Int { holeNumber }

    private enum CodingKeys: String, CodingKey {
        case par, yardage, handicap
        case holeNumber = "hole_number"
    }
}

struct CourseDetail: Decodable, Identifiable, Hashable {
    let id: String
    let name: String
    let clubName: String?
    let city: String?
    let state: String?
    let country: String?
    let holesCount: Int?
    let tees: [TeeBox]
    let holes: [HoleInfo]

    private enum CodingKeys: String, CodingKey {
        case id, name, city, state, country, tees, holes
        case clubName = "club_name"
        case holesCount = "holes_count"
        case teeData = "tee_data"
        case holeData = "hole_data"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        name = try c.decode(String.self, forKey: .name)
        clubName = try c.decodeIfPresent(String.self, forKey: .clubName)
        city = try c.decodeIfPresent(String.self, forKey: .city)
        state = try c.decodeIfPresent(String.self, forKey: .state)
        country = try c.decodeIfPresent(String.self, forKey: .country)
        holesCount = try c.decodeIfPresent(Int.self, forKey: .holesCount)
        tees = try c.decodeIfPresent([TeeBox].self, forKey: .tees)
            ?? c.decodeIfPresent([TeeBox].self, forKey: .teeData)
            ?? []
        holes = try c.decodeIfPresent([HoleInfo].self, forKey: .holes)
            ?? c.decodeIfPresent([HoleInfo].self, forKey: .holeData)
            ?? []
    }
}

struct CourseDetailResponse: Decodable {
    let source: String
    let course: CourseDetail
}

// MARK: - Round Handoff
//
// Produced when the player picks a course + tee. Consumed by the Scorecard
// Entry View (next task) to seed `course_id`, the selected tee, and the
// per-hole template (par/yardage) for the `POST /api/v1/rounds` payload.

struct RoundCourseSelection: Hashable {
    let courseId: String
    let courseName: String
    let city: String?
    let state: String?
    let tee: TeeBox
    let holes: [HoleInfo]

    var location: String {
        [city, state].compactMap { $0?.isEmpty == false ? $0 : nil }.joined(separator: ", ")
    }
}
