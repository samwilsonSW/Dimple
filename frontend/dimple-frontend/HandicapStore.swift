import Foundation

/// Local source of truth for the player's handicap index (UserDefaults).
/// A future `GET /api/v1/me` would sync this with the backend; for now it's local.
@Observable
final class HandicapStore {
    static let shared = HandicapStore()

    private let defaults = UserDefaults.standard
    private static let valueKey = "user_handicap_index"
    private static let dateKey = "handicap_set_date"
    private static let onboardedKey = "handicap_onboarded"

    private(set) var handicapIndex: Double?   // nil = never set
    private(set) var setDate: Date?
    private(set) var hasOnboarded: Bool       // saw the welcome screen (set or skipped)

    var isSet: Bool { handicapIndex != nil }

    private init() {
        // object(forKey:) distinguishes "unset" from a stored 0.0 (scratch golfer).
        if defaults.object(forKey: Self.valueKey) != nil {
            handicapIndex = defaults.double(forKey: Self.valueKey)
        }
        setDate = defaults.object(forKey: Self.dateKey) as? Date
        hasOnboarded = defaults.bool(forKey: Self.onboardedKey)
    }

    /// Stores a handicap, clamped to 0.0–54.0 and rounded to one decimal.
    func save(_ value: Double) {
        let clamped = min(max(value, 0.0), 54.0)
        let rounded = (clamped * 10).rounded() / 10
        handicapIndex = rounded
        setDate = Date()
        defaults.set(rounded, forKey: Self.valueKey)
        defaults.set(setDate, forKey: Self.dateKey)
        markOnboarded()
    }

    /// "I'll set this later" — leaves handicap unset but won't re-show the welcome
    /// screen; the round flow prompts before the first round instead.
    func markOnboarded() {
        hasOnboarded = true
        defaults.set(true, forKey: Self.onboardedKey)
    }
}
