import SwiftUI

// MARK: - Manual Course
//
// Fallback for courses GolfCourseAPI.com doesn't have — small courses, new
// courses, and secondary layouts like "Creek Course" at Meadowbrook. Collects
// the minimum the coach needs: name/location for context, and per-hole par so
// scores mean something.
//
// What this trades away (see docs/archive/MANUAL_COURSE_ENTRY_SPEC.md):
// no yardage, no tee box, so no rating/slope differential and no shot-by-shot.
// Scorecard stats, SG putting/approach, and coach access are unaffected.

struct ManualCourse: Codable, Hashable {
    let name: String
    let city: String
    let state: String
    let holes: Int          // 9 or 18
    let parValues: [Int]    // par 3–5, count == holes

    var totalPar: Int { parValues.reduce(0, +) }

    /// Scorecard template. Manual courses have no yardage or stroke index, so
    /// the entry screen simply omits the yardage line.
    var holeTemplate: [HoleInfo] {
        parValues.enumerated().map { index, par in
            HoleInfo(holeNumber: index + 1, par: par, yardage: nil, handicap: nil)
        }
    }
}

/// Navigation marker, pushed from Course Search when the player can't find
/// their course. NewRoundView owns the destination.
enum ManualCourseRoute: Hashable { case form }

// MARK: - View Model

@Observable
final class ManualCourseEntryViewModel {
    static let parRange = 3...5
    static let holeOptions = [9, 18]
    private static let defaultPar = 4

    var name = ""
    var city = ""
    var state = ""
    private(set) var holes = 18
    private(set) var parValues = Array(repeating: defaultPar, count: 18)

    // MARK: Derived

    var totalPar: Int { parValues.reduce(0, +) }

    var trimmedName: String { name.trimmingCharacters(in: .whitespacesAndNewlines) }
    var trimmedCity: String { city.trimmingCharacters(in: .whitespacesAndNewlines) }
    var normalizedState: String { state.trimmingCharacters(in: .whitespacesAndNewlines).uppercased() }

    var isValid: Bool {
        !trimmedName.isEmpty
            && !trimmedCity.isEmpty
            && normalizedState.count == 2
            && parValues.count == holes
            && parValues.allSatisfy { Self.parRange.contains($0) }
    }

    // MARK: Edits

    /// Growing 9 → 18 keeps the pars already edited on the front nine.
    func setHoles(_ count: Int) {
        guard count != holes, Self.holeOptions.contains(count) else { return }
        holes = count
        if parValues.count < count {
            parValues += Array(repeating: Self.defaultPar, count: count - parValues.count)
        } else {
            parValues = Array(parValues.prefix(count))
        }
    }

    /// Tap cycles 3 → 4 → 5 → 3. Beats eighteen steppers on screen, and it
    /// still works with a glove on.
    func cyclePar(at index: Int) {
        guard parValues.indices.contains(index) else { return }
        parValues[index] = parValues[index] >= Self.parRange.upperBound
            ? Self.parRange.lowerBound
            : parValues[index] + 1
    }

    func resetPars() {
        parValues = Array(repeating: Self.defaultPar, count: holes)
    }

    func makeCourse() -> ManualCourse? {
        guard isValid else { return nil }
        return ManualCourse(
            name: trimmedName,
            city: trimmedCity,
            state: normalizedState,
            holes: holes,
            parValues: parValues
        )
    }
}

// MARK: - Manual Course Entry View

struct ManualCourseEntryView: View {
    /// Hands the finished course up to the round flow, which continues to
    /// Round Setup exactly as an API course would.
    let onContinue: (RoundCourseSelection) -> Void

    @State private var vm = ManualCourseEntryViewModel()
    @FocusState private var focus: Field?

    private enum Field: Hashable { case name, city, state }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                intro
                detailsCard
                holesSection
                parSection
            }
            .padding()
            .padding(.bottom, 20)
        }
        .scrollDismissesKeyboard(.interactively)
        .navigationTitle("Enter Course")
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) { continueBar }
        .onAppear { focus = .name }
        .onChange(of: vm.name)  { _, v in vm.name = String(v.prefix(100)) }
        .onChange(of: vm.city)  { _, v in vm.city = String(v.prefix(50)) }
        .onChange(of: vm.state) { _, v in vm.state = String(v.uppercased().filter(\.isLetter).prefix(2)) }
    }

    private var intro: some View {
        Text("For courses the search can't find. You'll enter scores the same way — there's just no yardage or tee data to pull from.")
            .font(.subheadline)
            .foregroundStyle(Color(.secondaryLabel))
    }

    // MARK: Name / city / state

    private var detailsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Course", systemImage: "flag.fill")
                .font(.subheadline).fontWeight(.semibold)
                .foregroundStyle(Color.forestGreen)

            textField("Course name", text: $vm.name, field: .name, submit: .next)
                .textInputAutocapitalization(.words)

            HStack(spacing: 10) {
                textField("City", text: $vm.city, field: .city, submit: .next)
                    .textInputAutocapitalization(.words)
                textField("ST", text: $vm.state, field: .state, submit: .done)
                    .textInputAutocapitalization(.characters)
                    .frame(width: 74)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func textField(
        _ placeholder: String,
        text: Binding<String>,
        field: Field,
        submit: SubmitLabel
    ) -> some View {
        TextField(placeholder, text: text)
            .font(.body)
            .focused($focus, equals: field)
            .autocorrectionDisabled()
            .submitLabel(submit)
            .onSubmit { advance(from: field) }
            .padding(.vertical, 12).padding(.horizontal, 14)
            .background(Color(.tertiarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(focus == field ? Color.forestGreen.opacity(0.6) : Color(.separator), lineWidth: 1.5)
            )
    }

    private func advance(from field: Field) {
        switch field {
        case .name:  focus = .city
        case .city:  focus = .state
        case .state: focus = nil
        }
    }

    // MARK: Hole count

    private var holesSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("How many holes?")
                .font(.subheadline).fontWeight(.semibold)
                .foregroundStyle(Color(.secondaryLabel))

            HStack(spacing: 10) {
                ForEach(ManualCourseEntryViewModel.holeOptions, id: \.self) { count in
                    Button {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        vm.setHoles(count)
                    } label: {
                        Text("\(count) holes")
                            .font(.headline)
                            .foregroundStyle(vm.holes == count ? .white : Color(.label))
                            .frame(maxWidth: .infinity).frame(height: 50)
                            .background(vm.holes == count ? Color.forestGreen : Color(.secondarySystemBackground))
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    // MARK: Par editor

    private var parSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Par")
                    .font(.subheadline).fontWeight(.semibold)
                    .foregroundStyle(Color(.secondaryLabel))
                Spacer()
                Text("Total \(vm.totalPar)")
                    .font(.subheadline).fontWeight(.semibold)
                    .monospacedDigit().contentTransition(.numericText())
                    .foregroundStyle(Color.forestGreen)
            }

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 52), spacing: 8)], spacing: 8) {
                ForEach(Array(vm.parValues.indices), id: \.self) { index in
                    parCell(index)
                }
            }

            HStack {
                Text("Tap a hole to change its par.")
                    .font(.caption)
                    .foregroundStyle(Color(.tertiaryLabel))
                Spacer()
                Button("Reset to par 4") {
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    vm.resetPars()
                }
                .font(.caption).fontWeight(.semibold)
                .foregroundStyle(Color.forestGreen)
            }
        }
    }

    private func parCell(_ index: Int) -> some View {
        Button {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            vm.cyclePar(at: index)
        } label: {
            VStack(spacing: 1) {
                Text("\(index + 1)")
                    .font(.caption2)
                    .foregroundStyle(Color(.tertiaryLabel))
                Text("\(vm.parValues[index])")
                    .font(.system(.title3, design: .rounded)).fontWeight(.bold)
                    .monospacedDigit().contentTransition(.numericText())
                    .foregroundStyle(Color.forestGreen)
            }
            .frame(maxWidth: .infinity).frame(height: 54)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .stroke(Color(.separator), lineWidth: 0.5)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Hole \(index + 1), par \(vm.parValues[index])")
        .accessibilityHint("Changes par")
    }

    // MARK: Continue

    private var continueBar: some View {
        Button {
            guard let course = vm.makeCourse() else { return }
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            focus = nil
            onContinue(RoundCourseSelection(manual: course))
        } label: {
            Text("Continue to Scorecard")
                .font(.body).fontWeight(.semibold)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity).frame(height: 52)
                .background(vm.isValid ? Color.forestGreen : Color(.systemFill))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(!vm.isValid)
        .padding(.horizontal).padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }
}
