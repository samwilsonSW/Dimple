import SwiftUI

// MARK: - View Model

@Observable
final class RoundHistoryViewModel {
    enum State {
        case loading
        case empty
        case error(String)
        case loaded([RoundHistoryItem])
    }

    var state: State = .loading
    private var hasLoaded = false

    /// Called on each appearance — refreshes data, showing the skeleton only on
    /// the very first load so re-visiting the tab doesn't flicker.
    @MainActor func appear() async { await fetch(showSkeleton: !hasLoaded) }

    @MainActor func refresh() async { await fetch(showSkeleton: false) }

    @MainActor private func fetch(showSkeleton: Bool) async {
        if showSkeleton { state = .loading }
        do {
            let rounds = try await RoundHistoryService.shared.fetchRounds()
            hasLoaded = true
            withAnimation(.easeInOut(duration: 0.2)) {
                state = rounds.isEmpty ? .empty : .loaded(rounds)
            }
        } catch {
            // On a silent refresh that fails, keep showing whatever we have.
            if case .loaded = state, !showSkeleton { return }
            state = .error(error.localizedDescription)
        }
    }
}

// MARK: - Round History View

struct RoundHistoryView: View {
    var onNewRound: () -> Void = {}
    @State private var vm = RoundHistoryViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                switch vm.state {
                case .loading:
                    skeleton
                case .empty:
                    emptyState.frame(maxWidth: .infinity, minHeight: 440)
                case .error(let message):
                    errorState(message).frame(maxWidth: .infinity, minHeight: 440)
                case .loaded(let rounds):
                    list(rounds)
                }
            }
            .refreshable { await vm.refresh() }
            .navigationTitle("Round History")
            .navigationDestination(for: RoundHistoryItem.self) { RoundDetailView(round: $0) }
        }
        .task { await vm.appear() }
    }

    // MARK: List

    private func list(_ rounds: [RoundHistoryItem]) -> some View {
        LazyVStack(spacing: 12) {
            ForEach(rounds) { round in
                NavigationLink(value: round) { RoundCardView(round: round) }
                    .buttonStyle(.plain)
            }
            newRoundButton
                .padding(.top, 6)
        }
        .padding()
    }

    private var newRoundButton: some View {
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            onNewRound()
        } label: {
            Label("New Round", systemImage: "plus")
                .font(.body).fontWeight(.semibold).foregroundStyle(Color.forestGreen)
                .frame(maxWidth: .infinity).frame(height: 50)
                .background(Color.forestGreen.opacity(0.10))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
    }

    // MARK: Empty / Error / Skeleton

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "flag.fill")
                .font(.system(size: 44)).foregroundStyle(Color.forestGreen.opacity(0.4))
            Text("No rounds yet").font(.title3).fontWeight(.semibold)
            Text("Play a round and enter your scores to see them here.")
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center)
            Button {
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                onNewRound()
            } label: {
                Label("New Round", systemImage: "plus")
                    .font(.body).fontWeight(.semibold).foregroundStyle(.white)
                    .padding(.horizontal, 24).frame(height: 50)
                    .background(Color.forestGreen)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(.plain)
            .padding(.top, 4)
        }
        .padding(32)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40)).foregroundStyle(.orange)
            Text("Couldn't load rounds").font(.headline)
            Text(message).font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center).lineLimit(3)
            Text("Pull down to retry.").font(.caption).foregroundStyle(Color(.tertiaryLabel))
            Button("Try Again") { Task { await vm.refresh() } }
                .fontWeight(.semibold).foregroundStyle(Color.forestGreen).padding(.top, 4)
        }
        .padding(32)
    }

    private var skeleton: some View {
        LazyVStack(spacing: 12) {
            ForEach(0..<5, id: \.self) { _ in skeletonCard }
        }
        .padding()
    }

    private var skeletonCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            grayBar(160, 18)
            grayBar(110, 14)
            grayBar(90, 14)
            HStack(spacing: 8) { grayBar(46, 18); grayBar(46, 18); grayBar(46, 18); grayBar(46, 18) }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func grayBar(_ w: CGFloat, _ h: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: 5).fill(Color(.systemGray5)).frame(width: w, height: h)
    }
}

// MARK: - Round Card

struct RoundCardView: View {
    let round: RoundHistoryItem

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(round.course.displayName)
                    .font(.headline).lineLimit(1)
                Spacer(minLength: 8)
                if let vp = round.vsParText {
                    Text(vp).font(.headline).fontWeight(.bold)
                        .foregroundStyle(Color.scoreTone(round.vsPar ?? 0))
                }
            }

            HStack(alignment: .firstTextBaseline) {
                Text(round.course.location.isEmpty ? " " : round.course.location)
                    .font(.subheadline).foregroundStyle(Color(.secondaryLabel)).lineLimit(1)
                Spacer(minLength: 8)
                HStack(spacing: 4) {
                    Text(round.scoreText).font(.title3).fontWeight(.bold).monospacedDigit()
                    if let p = round.parText {
                        Text(p).font(.subheadline).foregroundStyle(Color(.secondaryLabel)).monospacedDigit()
                    }
                }
            }

            HStack {
                Text(round.displayDate).font(.caption).foregroundStyle(Color(.secondaryLabel))
                Spacer()
                if let g = round.girText {
                    Text(g).font(.caption).foregroundStyle(Color(.secondaryLabel))
                }
            }

            if round.hasStats {
                sgChips
            } else {
                Text("Stats unavailable")
                    .font(.caption).foregroundStyle(Color(.tertiaryLabel))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(alignment: .trailing) {
            Image(systemName: "chevron.right")
                .font(.caption).fontWeight(.semibold).foregroundStyle(Color(.tertiaryLabel))
                .padding(.trailing, 14)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(round.accessibilityText)
        .accessibilityHint("Double tap to view round details")
    }

    private var sgChips: some View {
        HStack(spacing: 8) {
            SGChip(letter: "G", value: round.stats?.sg_putting, category: .blue)    // putting
            SGChip(letter: "P", value: nil, category: .orange)                       // short game (TBD)
            SGChip(letter: "F", value: nil, category: .sageGreen)                     // driving (TBD)
            SGChip(letter: "A", value: round.stats?.sg_approach, category: .purple)   // approach
        }
    }
}

// MARK: - SG Chip

private struct SGChip: View {
    let letter: String
    let value: Double?     // nil → not yet calculated ("—")
    let category: Color

    var body: some View {
        let text = value.map { String(format: "%+.1f", $0) } ?? "—"
        let tone: Color = {
            guard let v = value else { return Color(.tertiaryLabel) }
            if v > 0.05 { return .sageGreen }
            if v < -0.05 { return .red }
            return Color(.secondaryLabel)
        }()
        return HStack(spacing: 3) {
            Text(letter).font(.caption2).fontWeight(.bold).foregroundStyle(category)
            Text(text).font(.caption2).fontWeight(.semibold).monospacedDigit().foregroundStyle(tone)
        }
        .padding(.horizontal, 8).padding(.vertical, 4)
        .background(category.opacity(0.10))
        .clipShape(Capsule())
    }
}

// MARK: - Round Detail (placeholder)

struct RoundDetailView: View {
    let round: RoundHistoryItem

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                VStack(spacing: 6) {
                    Text(round.scoreText)
                        .font(.system(size: 56, weight: .bold, design: .rounded)).monospacedDigit()
                    if let vp = round.vsParText {
                        Text(vp).font(.title3).fontWeight(.semibold)
                            .foregroundStyle(Color.scoreTone(round.vsPar ?? 0))
                    }
                    Text("\(round.course.displayName) · \(round.displayDate)")
                        .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 20)
                .background(Color.forestGreen.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

                if let s = round.stats {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                        statCard("GIR", percent(s.gir_percentage))
                        statCard("Fairways", fairways(s))
                        statCard("SG Putting", sg(s.sg_putting))
                        statCard("SG Approach", sg(s.sg_approach))
                        if let p = s.total_putts { statCard("Putts", "\(p)") }
                        if let a = s.avg_putts_per_hole { statCard("Putts / Hole", String(format: "%.1f", a)) }
                    }
                } else {
                    Text("Stats unavailable for this round.")
                        .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                }

                if let r = round.reflection, !r.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Label("Reflection", systemImage: "text.quote")
                            .font(.subheadline).fontWeight(.semibold).foregroundStyle(Color.champagneGold)
                        Text(r).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }

                Text("Full per-hole detail coming soon.")
                    .font(.caption).foregroundStyle(Color(.tertiaryLabel))
                    .padding(.top, 4)
            }
            .padding()
        }
        .navigationTitle(round.course.displayName)
        .navigationBarTitleDisplayMode(.inline)
    }

    private func statCard(_ title: String, _ value: String) -> some View {
        VStack(spacing: 6) {
            Text(value).font(.system(.title2, design: .rounded)).fontWeight(.bold).monospacedDigit()
            Text(title).font(.caption).foregroundStyle(Color(.secondaryLabel))
        }
        .frame(maxWidth: .infinity).padding(.vertical, 18)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func percent(_ v: Double?) -> String { v.map { "\(Int(($0 * 100).rounded()))%" } ?? "–" }
    private func fairways(_ s: RoundStats) -> String {
        if let h = s.fairways_hit, let p = s.fairways_possible, p > 0 { return "\(h)/\(p)" }
        return percent(s.fairway_percentage)
    }
    private func sg(_ v: Double?) -> String { v.map { String(format: "%+.1f", $0) } ?? "–" }
}
