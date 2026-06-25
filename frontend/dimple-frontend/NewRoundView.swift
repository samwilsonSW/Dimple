import SwiftUI

/// Owns the new-round flow: course search → tee picker → round setup →
/// scorecard entry → review → submit → summary. Holds the shared scorecard
/// view model and drives navigation via a typed path.
struct NewRoundView: View {
    @State private var path = NavigationPath()
    @State private var scorecardVM: ScorecardViewModel?
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
                .navigationDestination(for: RoundCourseSelection.self) { selection in
                    RoundSetupView(selection: selection) { start in
                        scorecardVM = ScorecardViewModel(start: start)
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
                scorecardVM = ScorecardViewModel(draft: draft)
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
        if let vm = scorecardVM {
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
                RoundSummaryView(stats: vm.result, courseName: vm.courseName, onDone: finishRound)
            }
        } else {
            // VM lost (shouldn't happen) — bail back to the search root.
            Color.clear.onAppear { path = NavigationPath() }
        }
    }

    private func maybeOfferResume() {
        guard path.isEmpty, scorecardVM == nil, let draft = DraftRoundStore.shared.load() else { return }
        pendingDraft = draft
        showResume = true
    }

    private func finishRound() {
        DraftRoundStore.shared.clear()
        scorecardVM = nil
        pendingDraft = nil
        path = NavigationPath()
    }
}
