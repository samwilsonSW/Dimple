import Foundation

struct DrillRecommendation: Decodable, Identifiable {
    var id: Int { priority }
    let priority: Int
    let focus_area: String
    let drill_name: String
    let instructions: String
    let expected_outcome: String
}

struct CoachResponse: Decodable {
    let answer: String
    let confidence: Int
    let key_insights: [String]
    let drill_recommendations: [DrillRecommendation]
}
