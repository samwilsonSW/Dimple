import SwiftUI

/// Holds the scorecard view model for one round.
///
/// Deliberately a reference box rather than the view model sitting in `@State`
/// directly. Starting a round sets the model and pushes the route in the same
/// closure, but a `@State` write doesn't land until the next render pass while
/// the push builds its destination immediately — so the destination read a nil
/// model and SwiftUI never rebuilt it. That race is bug #3: it surfaced first
/// as a kick back to course search, then as a spinner that never resolved
/// until you backed out and tapped Start Round a second time.
///
/// Mutating one long-lived object closes the gap: the destination reads the
/// model in the same transaction that set it. Nothing here needs to invalidate
/// the view — every mutation is paired with a `path` change that already does.
final class RoundFlow {
    var scorecard: ScorecardViewModel?
}

/// Owns the new-round flow: course search → tee picker → round setup →
/// scorecard entry → review → submit → summary. Holds the shared scorecard
/// view model and drives navigation via a typed path.
struct NewRoundView: View {
    @State private var path = NavigationPath()
    @State private var flow = RoundFlow()
    @State private var pendingDraft: DraftRound?
    @State private var showResume = false

    enum RoundRoute: Hashable { case entry, review, summary }

    var body: some View {
        NavigationStack(path: $path) {
            CourseSearchView()
                .navigationDestination(for: Course.self) { course in
                    CourseTeePickerView(course: course) { selection in
                        path.append(selection)
                    }
                }
                .navigationDestination(for: ManualCourseRoute.self) { _ in
                    ManualCourseEntryView { selection in
                        path.append(selection)
                    }
                }
                .navigationDestination(for: RoundCourseSelection.self) { selection in
                    RoundSetupView(selection: selection) { start in
                        flow.scorecard = ScorecardViewModel(start: start)
                        path.append(RoundRoute.entry)
                    }
                }
                .navigationDestination(for: RoundRoute.self) { route in
                    routeView(route)
                }
        }
        .onAppear(perform: maybeOfferResume)
        .alert("Resume round?", isPresented: $showResume, presenting: pendingDraft) { draft in
            Button("Resume") {
                flow.scorecard = ScorecardViewModel(draft: draft)
                path.append(RoundRoute.entry)
            }
            Button("Discard", role: .destructive) {
                DraftRoundStore.shared.clear()
                pendingDraft = nil
            }
            Button("Not now", role: .cancel) {}
        } message: { draft in
            Text("You have a round in progress at \(draft.courseName) (hole \(draft.currentHoleNumber)).")
        }
    }

    @ViewBuilder
    private func routeView(_ route: RoundRoute) -> some View {
        if let vm = flow.scorecard {
            switch route {
            case .entry:
                ScorecardEntryView(vm: vm, onReview: { path.append(RoundRoute.review) })
            case .review:
                ScorecardReviewView(
                    vm: vm,
                    onEditHole: { n in vm.jump(to: n); path.removeLast() },
                    onSubmitted: { path.append(RoundRoute.summary) }
                )
            case .summary:
                RoundSummaryView(stats: vm.result, courseName: vm.courseName, roundID: vm.roundID, onDone: finishRound)
            }
        } else {
            // Unreachable: every push of a RoundRoute sets flow.scorecard first,
            // and RoundFlow makes that write visible in the same transaction.
            // Kept as a neutral placeholder — never a path reset, which is what
            // originally read as being kicked back to course search.
            ProgressView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func maybeOfferResume() {
        guard path.isEmpty, flow.scorecard == nil, let draft = DraftRoundStore.shared.load() else { return }
        pendingDraft = draft
        showResume = true
    }

    private func finishRound() {
        DraftRoundStore.shared.clear()
        flow.scorecard = nil
        pendingDraft = nil
        path = NavigationPath()
    }
}
