import SwiftUI

// MARK: - Per-hole working state

struct HoleState: Identifiable, Hashable {
    let holeNumber: Int
    let par: Int
    let yardage: Int?
    var score: Int
    var putts: Int
    var fairway: Bool?   // nil = not recorded; always nil on par 3
    var gir: Bool?       // nil = not recorded
    var entered: Bool

    var id: Int { holeNumber }
    var isPar3: Bool { par == 3 }
    var toPar: Int { score - par }
}

// MARK: - View Model

@Observable
final class ScorecardViewModel {
    let courseId: String
    let courseName: String
    let city: String?
    let state: String?
    let teeBox: TeeBox
    let holeTemplate: [HoleInfo]
    let handicapIndex: Double
    let roundDate: String
    let mode: RoundMode

    var holes: [HoleState]
    var currentHoleNumber: Int

    var isSubmitting = false
    var submitError: String?
    var result: RoundStats?

    enum Nine { case front, back }
    var selectedNine: Nine

    init(start: ScorecardStart) {
        let sel = start.selection
        courseId = sel.courseId; courseName = sel.courseName
        city = sel.city; state = sel.state
        teeBox = sel.tee; holeTemplate = sel.holes
        handicapIndex = start.handicapIndex; roundDate = start.roundDate; mode = start.mode

        let nums = start.mode.holeNumbers(in: sel.holes)
        holes = nums.compactMap { n in
            guard let t = sel.holes.first(where: { $0.holeNumber == n }) else { return nil }
            return HoleState(holeNumber: n, par: t.par, yardage: t.yardage,
                             score: t.par, putts: min(2, max(t.par - 1, 0)),
                             fairway: nil, gir: nil, entered: false)
        }
        currentHoleNumber = nums.first ?? 1
        selectedNine = (nums.first ?? 1) <= 9 ? .front : .back
    }

    init(draft: DraftRound) {
        courseId = draft.courseId; courseName = draft.courseName
        city = draft.city; state = draft.state
        teeBox = draft.teeBox; holeTemplate = draft.holeTemplate
        handicapIndex = draft.handicapIndex; roundDate = draft.roundDate; mode = draft.mode

        let nums = draft.mode.holeNumbers(in: draft.holeTemplate)
        holes = nums.map { n in
            let t = draft.holeTemplate.first(where: { $0.holeNumber == n })
            let par = t?.par ?? 4
            if let e = draft.holes.first(where: { $0.holeNumber == n }) {
                return HoleState(holeNumber: n, par: e.par, yardage: e.yardage ?? t?.yardage,
                                 score: e.score, putts: e.putts ?? min(2, max(e.par - 1, 0)),
                                 fairway: e.fairway, gir: e.gir, entered: true)
            }
            return HoleState(holeNumber: n, par: par, yardage: t?.yardage,
                             score: par, putts: min(2, max(par - 1, 0)),
                             fairway: nil, gir: nil, entered: false)
        }
        currentHoleNumber = draft.currentHoleNumber
        selectedNine = draft.currentHoleNumber <= 9 ? .front : .back
    }

    // MARK: Derived

    var enteredHoles: [HoleState] { holes.filter(\.entered) }
    var totalStrokes: Int { enteredHoles.reduce(0) { $0 + $1.score } }
    var totalToPar: Int { enteredHoles.reduce(0) { $0 + $1.toPar } }
    var totalPutts: Int { enteredHoles.reduce(0) { $0 + $1.putts } }

    var hasFront: Bool { holes.contains { $0.holeNumber <= 9 } }
    var hasBack: Bool { holes.contains { $0.holeNumber >= 10 } }
    func holes(in nine: Nine) -> [HoleState] {
        holes.filter { nine == .front ? $0.holeNumber <= 9 : $0.holeNumber >= 10 }
    }

    var canSubmit: Bool {
        mode.allowsEarlySubmit ? !enteredHoles.isEmpty : enteredHoles.count == holes.count
    }

    private func idx(_ n: Int) -> Int? { holes.firstIndex { $0.holeNumber == n } }
    func position(of n: Int) -> Int? { holes.firstIndex { $0.holeNumber == n } }
    var isFirstHole: Bool { holes.first?.holeNumber == currentHoleNumber }
    var isLastHole: Bool { holes.last?.holeNumber == currentHoleNumber }

    // MARK: Edits (each marks the hole entered + autosaves the draft)

    func adjustScore(_ n: Int, _ delta: Int) {
        guard let i = idx(n) else { return }
        holes[i].score = max(1, holes[i].score + delta)
        applyAutoRules(&holes[i])
        holes[i].putts = min(holes[i].putts, max(holes[i].score - 1, 0))
        holes[i].entered = true
        autosave()
    }

    func adjustPutts(_ n: Int, _ delta: Int) {
        guard let i = idx(n) else { return }
        let maxP = max(holes[i].score - 1, 0)
        holes[i].putts = min(max(holes[i].putts + delta, 0), maxP)
        holes[i].entered = true
        autosave()
    }

    func setFairway(_ n: Int, _ value: Bool?) {
        guard let i = idx(n) else { return }
        holes[i].fairway = holes[i].isPar3 ? nil : value
        holes[i].entered = true
        autosave()
    }

    func setGir(_ n: Int, _ value: Bool?) {
        guard let i = idx(n) else { return }
        holes[i].gir = value
        holes[i].entered = true
        autosave()
    }

    /// Hole-in-one and eagle auto-fills (spec edge cases).
    private func applyAutoRules(_ h: inout HoleState) {
        if h.score == 1 {
            h.putts = 0
            h.gir = true
            h.fairway = h.isPar3 ? nil : true
        } else if h.score <= h.par - 2 {
            h.gir = true   // can't eagle without hitting the green in regulation
        }
    }

    /// Putts stepper is locked when score == 1 (hole-in-one ⇒ 0 putts).
    func puttsLocked(_ n: Int) -> Bool {
        guard let i = idx(n) else { return false }
        return holes[i].score <= 1
    }

    // MARK: Navigation

    func jump(to n: Int) {
        currentHoleNumber = n
        selectedNine = n <= 9 ? .front : .back
    }

    func next() {
        guard let p = position(of: currentHoleNumber) else { return }
        if let i = idx(currentHoleNumber) { holes[i].entered = true }
        if p + 1 < holes.count { jump(to: holes[p + 1].holeNumber) }
        autosave()
    }

    func previous() {
        guard let p = position(of: currentHoleNumber), p > 0 else { return }
        jump(to: holes[p - 1].holeNumber)
    }

    // MARK: Draft

    func autosave() {
        let entries = enteredHoles.map {
            HoleEntry(holeNumber: $0.holeNumber, par: $0.par, yardage: $0.yardage,
                      score: $0.score, putts: $0.putts, fairway: $0.fairway, gir: $0.gir)
        }
        let draft = DraftRound(
            courseId: courseId, courseName: courseName, city: city, state: state,
            teeBox: teeBox, holeTemplate: holeTemplate, handicapIndex: handicapIndex,
            roundDate: roundDate, mode: mode, currentHoleNumber: currentHoleNumber,
            holes: entries, lastSaved: Date()
        )
        DraftRoundStore.shared.save(draft)
    }

    // MARK: Submit

    @MainActor
    func submit() async -> Bool {
        isSubmitting = true
        submitError = nil
        let payloadHoles = enteredHoles.map {
            HolePayload(hole_number: $0.holeNumber, par: $0.par, yardage: $0.yardage,
                        score: $0.score, putts: $0.putts,
                        fairway: $0.isPar3 ? nil : $0.fairway, gir: $0.gir)
        }
        do {
            let resp = try await RoundService.shared.submit(
                courseId: courseId,
                course: CoursePayload(name: courseName, city: city, state: state),
                teeBox: TeeBoxPayload(tee_name: teeBox.teeName, rating: teeBox.rating, slope: teeBox.slope),
                handicapIndex: handicapIndex,
                roundDate: roundDate,
                holes: payloadHoles
            )
            result = resp.round_stats
            isSubmitting = false
            DraftRoundStore.shared.clear()
            return true
        } catch {
            submitError = error.localizedDescription
            isSubmitting = false
            return false
        }
    }
}

// MARK: - Scorecard Entry View (focused single hole)
//
// Three fixed zones per Duk's taste call:
//   Top    — current hole + running totals
//   Middle — fairway / GIR / putts (scrolls if tight)
//   Bottom — score +/- and the big primary action (pinned, thumb-reachable)
// The full all-holes scorecard lives behind the top-right "Scorecard" button.

struct ScorecardEntryView: View {
    let vm: ScorecardViewModel
    let onReview: () -> Void

    private var hole: HoleState? { vm.holes.first { $0.holeNumber == vm.currentHoleNumber } }

    var body: some View {
        Group {
            if let h = hole {
                VStack(spacing: 0) {
                    topZone(h)
                    Divider()
                    middleZone(h)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .padding(.horizontal)
                }
                .safeAreaInset(edge: .bottom) { bottomZone(h) }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    onReview()
                } label: { Label("Scorecard", systemImage: "list.bullet.rectangle") }
            }
        }
    }

    // MARK: Top — hole + running totals

    private func topZone(_ h: HoleState) -> some View {
        VStack(spacing: 10) {
            VStack(spacing: 2) {
                Text("Hole \(h.holeNumber)")
                    .font(.system(.title, design: .rounded)).fontWeight(.bold)
                HStack(spacing: 6) {
                    Text("Par \(h.par)")
                    if let y = h.yardage, y > 0 { Text("· \(y) yds") }
                }
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
            }
            .frame(maxWidth: .infinity)
            HStack(spacing: 0) {
                stat("To Par", formatToPar(vm.totalToPar), color: Color.scoreTone(vm.totalToPar))
                divider
                stat("Strokes", "\(vm.totalStrokes)")
                divider
                stat("Putts", "\(vm.totalPutts)")
            }
        }
        .padding(.horizontal).padding(.top, 8).padding(.bottom, 12)
        .background(Color(.secondarySystemBackground))
    }

    private func stat(_ title: String, _ value: String, color: Color = Color(.label)) -> some View {
        VStack(spacing: 3) {
            Text(value).font(.system(.title3, design: .rounded)).fontWeight(.bold)
                .foregroundStyle(color).monospacedDigit().contentTransition(.numericText())
            Text(title).font(.caption2).foregroundStyle(Color(.secondaryLabel))
                .textCase(.uppercase).kerning(0.5)
        }
        .frame(maxWidth: .infinity)
    }

    private var divider: some View { Rectangle().fill(Color(.separator)).frame(width: 0.5, height: 30) }

    // MARK: Middle — fairway / GIR / putts

    private func middleZone(_ h: HoleState) -> some View {
        VStack(spacing: 0) {
            Spacer(minLength: 12)
            if !h.isPar3 {
                field("Fairway") {
                    TriToggle(leftLabel: "Missed", rightLabel: "Hit", value: h.fairway) {
                        vm.setFairway(h.holeNumber, $0)
                    }
                }
                Spacer(minLength: 12)
            }
            field("Green in Regulation") {
                TriToggle(leftLabel: "No", rightLabel: "Yes", value: h.gir) {
                    vm.setGir(h.holeNumber, $0)
                }
            }
            Spacer(minLength: 12)
            puttsField(h)
            Spacer(minLength: 12)
        }
    }

    private func field<Content: View>(_ label: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(spacing: 12) {
            Text(label).font(.headline)
            content()
        }
        .frame(maxWidth: .infinity)
    }

    private func puttsField(_ h: HoleState) -> some View {
        VStack(spacing: 12) {
            Text("Putts").font(.headline)
            BigStepper(
                valueText: "\(h.putts)", size: .small,
                minusEnabled: !vm.puttsLocked(h.holeNumber) && h.putts > 0,
                plusEnabled: !vm.puttsLocked(h.holeNumber) && h.putts < max(h.score - 1, 0),
                onMinus: { vm.adjustPutts(h.holeNumber, -1) },
                onPlus:  { vm.adjustPutts(h.holeNumber, +1) }
            )
            if vm.puttsLocked(h.holeNumber) {
                Text("Hole-in-one").font(.caption2).foregroundStyle(Color(.tertiaryLabel))
            }
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: Bottom — score + primary action (pinned thumb zone)

    private func bottomZone(_ h: HoleState) -> some View {
        VStack(spacing: 14) {
            HStack(spacing: 8) {
                Text("Score").font(.headline)
                Text(formatToPar(h.toPar)).font(.subheadline).fontWeight(.semibold)
                    .foregroundStyle(Color.scoreTone(h.toPar))
            }
            .frame(maxWidth: .infinity)
            BigStepper(
                valueText: "\(h.score)", size: .large,
                minusEnabled: h.score > 1, plusEnabled: true,
                onMinus: { vm.adjustScore(h.holeNumber, -1) },
                onPlus:  { vm.adjustScore(h.holeNumber, +1) }
            )
            actionRow
        }
        .padding(.horizontal).padding(.top, 12).padding(.bottom, 8)
        .background(.ultraThinMaterial)
    }

    private var actionRow: some View {
        HStack(spacing: 12) {
            if !vm.isFirstHole {
                Button {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    vm.previous()
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.headline).foregroundStyle(Color.forestGreen)
                        .frame(width: 64, height: 54)
                        .background(Color.forestGreen.opacity(0.10))
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .buttonStyle(.plain)
            }
            if vm.isLastHole {
                primaryButton("Review & Submit", system: "checkmark") { onReview() }
            } else {
                primaryButton("Next Hole", system: "chevron.right") { vm.next() }
            }
        }
    }

    private func primaryButton(_ title: String, system: String, action: @escaping () -> Void) -> some View {
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            action()
        } label: {
            HStack(spacing: 6) { Text(title); Image(systemName: system) }
                .font(.title3).fontWeight(.semibold).foregroundStyle(.white)
                .frame(maxWidth: .infinity).frame(height: 54)
                .background(Color.forestGreen)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}
