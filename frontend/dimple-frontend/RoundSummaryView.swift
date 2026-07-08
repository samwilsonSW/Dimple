import SwiftUI

struct RoundSummaryView: View {
    let stats: RoundStats?
    let courseName: String
    let onDone: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                successHeader
                if let s = stats {
                    scoreCard(s)
                    statsGrid(s)
                } else {
                    Text("Round saved. Stats will appear once processed.")
                        .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                        .multilineTextAlignment(.center)
                }
            }
            .padding()
            .padding(.bottom, 24)
        }
        .navigationTitle("Round Saved")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .safeAreaInset(edge: .bottom) { doneBar }
    }

    private var successHeader: some View {
        VStack(spacing: 12) {
            Circle().fill(Color.sageGreen.opacity(0.15)).frame(width: 72, height: 72)
                .overlay { Image(systemName: "checkmark").font(.system(size: 32, weight: .bold)).foregroundStyle(Color.sageGreen) }
            Text("Round Saved!").font(.system(.title2, design: .rounded)).fontWeight(.bold)
            Text(courseName).font(.subheadline).foregroundStyle(Color(.secondaryLabel))
        }
        .padding(.top, 8)
    }

    private func scoreCard(_ s: RoundStats) -> some View {
        let toPar = s.strokes_over_under.map { Int($0.rounded()) }
        return VStack(spacing: 6) {
            Text(s.total_score.map { "\($0)" } ?? "–")
                .font(.system(size: 56, weight: .bold, design: .rounded)).monospacedDigit()
            if let tp = toPar {
                Text(formatToPar(tp)).font(.title3).fontWeight(.semibold)
                    .foregroundStyle(Color.scoreTone(tp))
            }
            Text("Total Score").font(.caption).foregroundStyle(Color(.secondaryLabel))
                .textCase(.uppercase).kerning(0.5)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 20)
        .background(Color.forestGreen.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func statsGrid(_ s: RoundStats) -> some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            statCard("GIR", percent(s.gir_percentage), accent: .sageGreen)
            statCard("Fairways", fairwayText(s), accent: .sageGreen)
            statCard("SG Putting", sg(s.sg_putting), accent: sgColor(s.sg_putting))
            statCard("SG Approach", sg(s.sg_approach), accent: sgColor(s.sg_approach))
            if let p = s.total_putts { statCard("Putts", "\(p)") }
            if let a = s.avg_putts_per_hole { statCard("Putts / Hole", String(format: "%.1f", a)) }
        }
    }

    private func statCard(_ title: String, _ value: String, accent: Color = Color(.label)) -> some View {
        VStack(spacing: 6) {
            Text(value).font(.system(.title2, design: .rounded)).fontWeight(.bold)
                .foregroundStyle(accent).monospacedDigit()
            Text(title).font(.caption).foregroundStyle(Color(.secondaryLabel))
        }
        .frame(maxWidth: .infinity).padding(.vertical, 18)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private var doneBar: some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            onDone()
        } label: {
            Text("Done").font(.body).fontWeight(.semibold).foregroundStyle(.white)
                .frame(maxWidth: .infinity).frame(height: 52)
                .background(Color.forestGreen)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .padding(.horizontal).padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    // MARK: Formatting

    private func percent(_ v: Double?) -> String {
        guard let v else { return "–" }
        return "\(Int((v * 100).rounded()))%"
    }
    private func fairwayText(_ s: RoundStats) -> String {
        if let hit = s.fairways_hit, let poss = s.fairways_possible, poss > 0 {
            return "\(hit)/\(poss)"
        }
        return percent(s.fairway_percentage)
    }
    private func sg(_ v: Double?) -> String {
        guard let v else { return "–" }
        return String(format: "%+.1f", v)
    }
    private func sgColor(_ v: Double?) -> Color {
        guard let v else { return Color(.label) }
        if v > 0.05 { return .sageGreen }
        if v < -0.05 { return .red }
        return Color(.label)
    }
}
