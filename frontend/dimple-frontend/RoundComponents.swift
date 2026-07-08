import SwiftUI

// MARK: - Big Stepper
//
// Sun-readable, glove-friendly +/- control. Large variant for score/handicap,
// small for putts. Tap targets ≥ 44pt per the spec.

struct BigStepper: View {
    enum Size { case large, small }

    let valueText: String
    var size: Size = .large
    var minusEnabled: Bool = true
    var plusEnabled: Bool = true
    let onMinus: () -> Void
    let onPlus: () -> Void

    private var diameter: CGFloat { size == .large ? 56 : 44 }
    private var glyph: CGFloat { size == .large ? 26 : 20 }
    private var valueFont: Font {
        size == .large ? .system(size: 40, weight: .bold, design: .rounded)
                       : .system(size: 26, weight: .semibold, design: .rounded)
    }
    private var valueWidth: CGFloat { size == .large ? 84 : 56 }

    var body: some View {
        HStack(spacing: size == .large ? 18 : 12) {
            button(systemName: "minus", enabled: minusEnabled, action: onMinus)
            Text(valueText)
                .font(valueFont)
                .monospacedDigit()
                .frame(minWidth: valueWidth)
                .contentTransition(.numericText())
            button(systemName: "plus", enabled: plusEnabled, action: onPlus)
        }
    }

    private func button(systemName: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            action()
        } label: {
            Circle()
                .fill(enabled ? Color.forestGreen : Color(.systemFill))
                .frame(width: diameter, height: diameter)
                .overlay {
                    Image(systemName: systemName)
                        .font(.system(size: glyph, weight: .bold))
                        .foregroundStyle(enabled ? .white : Color(.tertiaryLabel))
                }
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
    }
}

// MARK: - Tri-state Toggle (Missed/Hit, No/Yes — or unrecorded)

struct TriToggle: View {
    let leftLabel: String    // false
    let rightLabel: String   // true
    let value: Bool?         // nil = not recorded
    let onChange: (Bool?) -> Void

    var body: some View {
        HStack(spacing: 10) {
            segment(label: leftLabel, isOn: value == false, tint: .red) {
                onChange(value == false ? nil : false)
            }
            segment(label: rightLabel, isOn: value == true, tint: .sageGreen) {
                onChange(value == true ? nil : true)
            }
        }
    }

    private func segment(label: String, isOn: Bool, tint: Color, action: @escaping () -> Void) -> some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            action()
        } label: {
            Text(label)
                .font(.headline)
                .foregroundStyle(isOn ? .white : Color(.label))
                .frame(maxWidth: .infinity)
                .frame(height: 44)
                .background(isOn ? tint : Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .stroke(isOn ? Color.clear : Color(.separator), lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Score color helper

extension Color {
    /// Green under par, red over, primary at even.
    static func scoreTone(_ relativeToPar: Int) -> Color {
        if relativeToPar < 0 { return .sageGreen }
        if relativeToPar > 0 { return .red }
        return Color(.label)
    }
}

/// "+3" / "E" / "-2" formatting for over/under par.
func formatToPar(_ value: Int) -> String {
    if value == 0 { return "E" }
    return value > 0 ? "+\(value)" : "\(value)"
}
