import SwiftUI

struct HandicapSetupView: View {
    enum Mode { case welcome, settings }

    let mode: Mode
    var onDone: () -> Void = {}

    @Environment(\.dismiss) private var dismiss
    @State private var value: Double
    @FocusState private var fieldFocused: Bool
    private let store = HandicapStore.shared

    init(mode: Mode, onDone: @escaping () -> Void = {}) {
        self.mode = mode
        self.onDone = onDone
        _value = State(initialValue: HandicapStore.shared.handicapIndex ?? 0.0)
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 24) {
                    if mode == .welcome { header }

                    Text("What's your handicap index?")
                        .font(.system(.title3, design: .rounded))
                        .fontWeight(.semibold)
                        .multilineTextAlignment(.center)

                    TextField("0.0", value: $value, format: .number.precision(.fractionLength(1)))
                        .keyboardType(.decimalPad)
                        .focused($fieldFocused)
                        .multilineTextAlignment(.center)
                        .font(.system(size: 56, weight: .bold, design: .rounded))
                        .frame(maxWidth: .infinity)

                    BigStepper(
                        valueText: "",
                        minusEnabled: value > 0.0,
                        plusEnabled: value < 54.0,
                        onMinus: { value = round1(max(0.0, value - 0.1)) },
                        onPlus:  { value = round1(min(54.0, value + 0.1)) }
                    )
                    .overlay(alignment: .center) {
                        Text("0.1")
                            .font(.caption2)
                            .foregroundStyle(Color(.tertiaryLabel))
                            .offset(y: 36)
                    }

                    Text("This helps us calculate strokes-gained analytics.")
                        .font(.subheadline)
                        .foregroundStyle(Color(.secondaryLabel))
                        .multilineTextAlignment(.center)

                    if mode == .settings, let d = store.setDate {
                        Text("Last updated \(d.formatted(date: .abbreviated, time: .omitted))")
                            .font(.caption)
                            .foregroundStyle(Color(.tertiaryLabel))
                    }
                }
                .padding(.horizontal, 28)
                .padding(.top, mode == .welcome ? 60 : 24)
            }
            .scrollDismissesKeyboard(.interactively)

            footer
                .padding(.horizontal, 28)
                .padding(.bottom, 20)
        }
        .background(Color(.systemBackground))
        .navigationTitle(mode == .settings ? "Handicap Index" : "")
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: value) { _, v in value = min(max(v, 0.0), 54.0) }
    }

    private var header: some View {
        VStack(spacing: 14) {
            Circle()
                .fill(Color.forestGreen)
                .frame(width: 72, height: 72)
                .overlay { Image(systemName: "flag.fill").font(.system(size: 32)).foregroundStyle(.white) }
                .shadow(color: Color.forestGreen.opacity(0.3), radius: 16, y: 6)
            Text("Welcome to Dimple")
                .font(.system(size: 32, weight: .bold, design: .rounded))
        }
    }

    private var footer: some View {
        VStack(spacing: 12) {
            Button {
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                store.save(value)
                finish()
            } label: {
                Text(mode == .welcome ? "Get Started" : "Save")
                    .font(.body).fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity).frame(height: 52)
                    .background(Color.forestGreen)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(.plain)

            if mode == .welcome {
                Button {
                    store.markOnboarded()
                    finish()
                } label: {
                    Text("I'll set this later")
                        .font(.subheadline)
                        .foregroundStyle(Color(.secondaryLabel))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func finish() {
        fieldFocused = false
        onDone()
        if mode == .settings { dismiss() }
    }

    private func round1(_ v: Double) -> Double { (v * 10).rounded() / 10 }
}
