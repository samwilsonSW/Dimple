import SwiftUI

struct ScorecardReviewView: View {
    let vm: ScorecardViewModel
    let onEditHole: (Int) -> Void
    let onSubmitted: () -> Void

    @State private var confirming = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                courseHeader
                if vm.hasFront { nineTable("Front 9", holes: vm.holes(in: .front)) }
                if vm.hasBack  { nineTable("Back 9",  holes: vm.holes(in: .back)) }
                summary
                if let err = vm.submitError { errorCard(err) }
                submitButton
            }
            .padding()
            .padding(.bottom, 24)
        }
        .navigationTitle("Review Round")
        .navigationBarTitleDisplayMode(.inline)
        .overlay { if vm.isSubmitting { loadingOverlay } }
        .alert("Submit this round?", isPresented: $confirming) {
            Button("Cancel", role: .cancel) {}
            Button("Submit") { Task { if await vm.submit() { onSubmitted() } } }
        } message: {
            Text("Submit round for \(vm.courseName)? This can't be undone.")
        }
    }

    private var courseHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(vm.courseName).font(.title3).fontWeight(.bold)
            Text("\(vm.teeBox.teeName) tees · \(displayDate(vm.roundDate))")
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
        }
    }

    // MARK: Table

    private func nineTable(_ title: String, holes: [HoleState]) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.subheadline).fontWeight(.semibold)
                .foregroundStyle(Color.forestGreen)
            headerRow
            ForEach(holes) { h in
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    onEditHole(h.holeNumber)
                } label: { dataRow(h) }
                .buttonStyle(.plain)
            }
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var headerRow: some View {
        HStack(spacing: 0) {
            cell("Hole", w: 44, bold: true)
            cell("Par", w: 40, bold: true)
            cell("Yds", w: 52, bold: true)
            cell("Score", w: 52, bold: true)
            cell("Putt", w: 44, bold: true)
            cell("FW", w: 34, bold: true)
            cell("GIR", w: 38, bold: true)
        }
        .foregroundStyle(Color(.secondaryLabel))
    }

    private func dataRow(_ h: HoleState) -> some View {
        HStack(spacing: 0) {
            cell("\(h.holeNumber)", w: 44)
            cell("\(h.par)", w: 40)
            cell(h.yardage.map { "\($0)" } ?? "–", w: 52)
            if h.entered {
                cell("\(h.score)", w: 52, color: .scoreTone(h.toPar), bold: true)
                cell("\(h.putts)", w: 44)
                cell(h.isPar3 ? "–" : mark(h.fairway), w: 34)
                cell(mark(h.gir), w: 38)
            } else {
                cell("–", w: 52); cell("–", w: 44); cell("–", w: 34); cell("–", w: 38)
            }
        }
        .padding(.vertical, 6)
        .overlay(alignment: .bottom) { Rectangle().fill(Color(.separator).opacity(0.5)).frame(height: 0.5) }
    }

    private func cell(_ text: String, w: CGFloat, color: Color = Color(.label), bold: Bool = false) -> some View {
        Text(text)
            .font(.caption).fontWeight(bold ? .semibold : .regular)
            .monospacedDigit().foregroundStyle(color)
            .frame(width: w)
            .minimumScaleFactor(0.7).lineLimit(1)
    }

    private func mark(_ v: Bool?) -> String {
        guard let v else { return "–" }
        return v ? "✓" : "✗"
    }

    // MARK: Summary

    private var summary: some View {
        let entered = vm.enteredHoles
        let fwPossible = entered.filter { !$0.isPar3 }.count
        let fwHit = entered.filter { $0.fairway == true }.count
        let girCount = entered.filter { $0.gir == true }.count
        return VStack(spacing: 10) {
            HStack {
                Text("Total").font(.headline)
                Spacer()
                Text("\(vm.totalStrokes)").font(.title3).fontWeight(.bold).monospacedDigit()
                Text("(\(formatToPar(vm.totalToPar)))")
                    .font(.headline).foregroundStyle(Color.scoreTone(vm.totalToPar))
            }
            HStack(spacing: 16) {
                metric("Putts", "\(vm.totalPutts)")
                metric("Fairways", fwPossible > 0 ? "\(fwHit)/\(fwPossible)" : "–")
                metric("GIR", entered.isEmpty ? "–" : "\(girCount)/\(entered.count)")
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity)
        .background(Color.forestGreen.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.headline).monospacedDigit()
            Text(title).font(.caption2).foregroundStyle(Color(.secondaryLabel))
        }
        .frame(maxWidth: .infinity)
    }

    private func errorCard(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
            Text(message).font(.subheadline)
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var submitButton: some View {
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            confirming = true
        } label: {
            Text(vm.isSubmitting ? "Saving…" : "Submit Round")
                .font(.body).fontWeight(.semibold).foregroundStyle(.white)
                .frame(maxWidth: .infinity).frame(height: 52)
                .background(vm.canSubmit ? Color.forestGreen : Color(.systemFill))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(!vm.canSubmit || vm.isSubmitting)
    }

    private var loadingOverlay: some View {
        ZStack {
            Color.black.opacity(0.2).ignoresSafeArea()
            VStack(spacing: 12) {
                ProgressView().tint(Color.forestGreen)
                Text("Saving round…").font(.subheadline)
            }
            .padding(24)
            .background(.regularMaterial)
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }
}
