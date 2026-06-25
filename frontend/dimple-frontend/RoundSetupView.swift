import SwiftUI

struct RoundSetupView: View {
    let selection: RoundCourseSelection
    let onStart: (ScorecardStart) -> Void

    @State private var handicap: Double
    @State private var mode: RoundMode = .full18
    @FocusState private var hcpFocused: Bool
    private let store = HandicapStore.shared

    init(selection: RoundCourseSelection, onStart: @escaping (ScorecardStart) -> Void) {
        self.selection = selection
        self.onStart = onStart
        _handicap = State(initialValue: HandicapStore.shared.handicapIndex ?? 0.0)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                courseHeader
                handicapCard
                modeSection
            }
            .padding()
            .padding(.bottom, 20)
        }
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle("Round Setup")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) { startBar }
        .onChange(of: handicap) { _, v in handicap = min(max(v, 0.0), 54.0) }
    }

    private var courseHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(selection.courseName)
                .font(.title3).fontWeight(.bold)
            HStack(spacing: 6) {
                if !selection.location.isEmpty { Text(selection.location) }
                Text("•")
                Text("\(selection.tee.teeName) tees")
            }
            .font(.subheadline)
            .foregroundStyle(Color(.secondaryLabel))
        }
    }

    private var handicapCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Handicap Index", systemImage: "person.fill")
                .font(.subheadline).fontWeight(.semibold)
                .foregroundStyle(Color.forestGreen)

            HStack(spacing: 16) {
                TextField("0.0", value: $handicap, format: .number.precision(.fractionLength(1)))
                    .keyboardType(.decimalPad)
                    .focused($hcpFocused)
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .frame(width: 90)
                Spacer()
                BigStepper(
                    valueText: "",
                    size: .small,
                    minusEnabled: handicap > 0.0,
                    plusEnabled: handicap < 54.0,
                    onMinus: { handicap = round1(max(0.0, handicap - 0.1)) },
                    onPlus:  { handicap = round1(min(54.0, handicap + 0.1)) }
                )
            }

            Text(store.isSet
                 ? "Pre-filled from your profile. Editing here applies to this round only."
                 : "Set once — we'll remember it for next time.")
                .font(.caption)
                .foregroundStyle(Color(.tertiaryLabel))
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private var modeSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("How many holes?")
                .font(.subheadline).fontWeight(.semibold)
                .foregroundStyle(Color(.secondaryLabel))
            ForEach(RoundMode.allCases) { m in
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    mode = m
                } label: { modeRow(m) }
                .buttonStyle(.plain)
            }
        }
    }

    private func modeRow(_ m: RoundMode) -> some View {
        let selected = mode == m
        return HStack(spacing: 14) {
            Image(systemName: m.systemImage)
                .font(.title3)
                .foregroundStyle(selected ? .white : Color.forestGreen)
                .frame(width: 30)
            VStack(alignment: .leading, spacing: 2) {
                Text(m.title).font(.headline)
                    .foregroundStyle(selected ? .white : Color(.label))
                Text(m.subtitle).font(.caption)
                    .foregroundStyle(selected ? Color.white.opacity(0.85) : Color(.secondaryLabel))
            }
            Spacer()
            if selected { Image(systemName: "checkmark.circle.fill").foregroundStyle(.white) }
        }
        .padding(14)
        .background(selected ? Color.forestGreen : Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var startBar: some View {
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            hcpFocused = false
            // First-time handicap entry becomes the stored default; later edits are per-round only.
            if !store.isSet { store.save(handicap) }
            onStart(ScorecardStart(
                selection: selection,
                mode: mode,
                handicapIndex: round1(handicap),
                roundDate: isoDateToday()
            ))
        } label: {
            Text("Start Round")
                .font(.body).fontWeight(.semibold).foregroundStyle(.white)
                .frame(maxWidth: .infinity).frame(height: 52)
                .background(Color.forestGreen)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .padding(.horizontal).padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    private func round1(_ v: Double) -> Double { (v * 10).rounded() / 10 }
}
