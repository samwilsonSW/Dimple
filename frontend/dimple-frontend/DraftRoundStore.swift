import Foundation

/// Persists a single in-progress round locally so it survives app kill / crash.
/// One active draft at a time — matches the "you have a round in progress" UX.
final class DraftRoundStore {
    static let shared = DraftRoundStore()

    private let defaults = UserDefaults.standard
    private static let key = "draft_round_current"

    var hasDraft: Bool { defaults.data(forKey: Self.key) != nil }

    func save(_ draft: DraftRound) {
        guard let data = try? JSONEncoder().encode(draft) else { return }
        defaults.set(data, forKey: Self.key)
    }

    func load() -> DraftRound? {
        guard let data = defaults.data(forKey: Self.key) else { return nil }
        return try? JSONDecoder().decode(DraftRound.self, from: data)
    }

    func clear() {
        defaults.removeObject(forKey: Self.key)
    }
}
