import SwiftUI

/// The expanded, active hole — steppers + toggles + navigation.
struct HoleEntryView: View {
    let vm: ScorecardViewModel
    let holeNumber: Int
    let onReview: () -> Void

    private var hole: HoleState? { vm.holes.first { $0.holeNumber == holeNumber } }

    var body: some View {
        if let h = hole {
            VStack(spacing: 18) {
                header(h)
                scoreRow(h)
                Divider()
                puttsRow(h)
                if !h.isPar3 {
                    fairwayRow(h)
                }
                girRow(h)
                navRow
            }
            .padding(18)
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Color.forestGreen.opacity(0.35), lineWidth: 1.5)
            )
            .shadow(color: .black.opacity(0.06), radius: 10, y: 4)
        }
    }

    private func header(_ h: HoleState) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text("Hole \(h.holeNumber)")
                .font(.system(.title2, design: .rounded)).fontWeight(.bold)
            Spacer()
            Text("Par \(h.par)").font(.headline).foregroundStyle(Color(.secondaryLabel))
            if let y = h.yardage, y > 0 {
                Text("· \(y) yds").font(.subheadline).foregroundStyle(Color(.tertiaryLabel))
            }
        }
    }

    private func scoreRow(_ h: HoleState) -> some View {
        VStack(spacing: 8) {
            HStack {
                Text("Score").font(.headline)
                Spacer()
                Text(formatToPar(h.toPar))
                    .font(.subheadline).fontWeight(.semibold)
                    .foregroundStyle(Color.scoreTone(h.toPar))
            }
            BigStepper(
                valueText: "\(h.score)",
                size: .large,
                minusEnabled: h.score > 1,
                plusEnabled: true,
                onMinus: { vm.adjustScore(holeNumber, -1) },
                onPlus:  { vm.adjustScore(holeNumber, +1) }
            )
        }
    }

    private func puttsRow(_ h: HoleState) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Putts").font(.headline)
                if vm.puttsLocked(holeNumber) {
                    Text("Hole-in-one").font(.caption2).foregroundStyle(Color(.tertiaryLabel))
                }
            }
            Spacer()
            BigStepper(
                valueText: "\(h.putts)",
                size: .small,
                minusEnabled: !vm.puttsLocked(holeNumber) && h.putts > 0,
                plusEnabled: !vm.puttsLocked(holeNumber) && h.putts < max(h.score - 1, 0),
                onMinus: { vm.adjustPutts(holeNumber, -1) },
                onPlus:  { vm.adjustPutts(holeNumber, +1) }
            )
        }
    }

    private func fairwayRow(_ h: HoleState) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Fairway").font(.headline)
            TriToggle(leftLabel: "Missed", rightLabel: "Hit", value: h.fairway) {
                vm.setFairway(holeNumber, $0)
            }
        }
    }

    private func girRow(_ h: HoleState) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Green in Regulation").font(.headline)
            TriToggle(leftLabel: "No", rightLabel: "Yes", value: h.gir) {
                vm.setGir(holeNumber, $0)
            }
        }
    }

    private var navRow: some View {
        HStack(spacing: 12) {
            if !vm.isFirstHole {
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    vm.previous()
                } label: {
                    Label("Previous", systemImage: "chevron.left")
                        .font(.subheadline).fontWeight(.semibold)
                        .foregroundStyle(Color.forestGreen)
                        .frame(maxWidth: .infinity).frame(height: 50)
                        .background(Color.forestGreen.opacity(0.10))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .buttonStyle(.plain)
            }

            if vm.isLastHole {
                Button {
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    onReview()
                } label: { primaryLabel("Review & Submit", system: "checkmark") }
                .buttonStyle(.plain)
            } else {
                Button {
                    UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                    vm.next()
                } label: { primaryLabel("Next Hole", system: "chevron.right") }
                .buttonStyle(.plain)
            }
        }
    }

    private func primaryLabel(_ text: String, system: String) -> some View {
        HStack(spacing: 6) {
            Text(text)
            Image(systemName: system)
        }
        .font(.body).fontWeight(.semibold).foregroundStyle(.white)
        .frame(maxWidth: .infinity).frame(height: 50)
        .background(Color.forestGreen)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
