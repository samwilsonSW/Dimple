import SwiftUI

// MARK: - Search View Model

@Observable
class CourseSearchViewModel {
    var query = ""
    var courses: [Course] = []
    var isLoading = false
    var errorMessage: String?
    var hasSearched = false

    @ObservationIgnored private var searchTask: Task<Void, Never>?

    /// Debounced search — fires 300ms after the player stops typing so we don't
    /// hammer the (rate-limited) course API on every keystroke.
    func queryChanged() {
        searchTask?.cancel()

        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count >= 2 else {
            courses = []
            errorMessage = nil
            isLoading = false
            hasSearched = false
            return
        }

        isLoading = true
        errorMessage = nil
        searchTask = Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            await performSearch(trimmed)
        }
    }

    @MainActor
    private func performSearch(_ q: String) async {
        do {
            let results = try await CourseService.shared.search(query: q)
            guard !Task.isCancelled else { return }
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                courses = results
                isLoading = false
                hasSearched = true
            }
        } catch {
            guard !Task.isCancelled else { return }
            withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                errorMessage = error.localizedDescription
                courses = []
                isLoading = false
                hasSearched = true
            }
        }
    }
}

// MARK: - Course Search View

struct CourseSearchView: View {
    @State private var vm = CourseSearchViewModel()
    @FocusState private var searchFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            searchBar
                .padding(.horizontal)
                .padding(.top, 8)
                .padding(.bottom, 12)

            content
        }
        .navigationTitle("New Round")
        .navigationBarTitleDisplayMode(.large)
        .onAppear { searchFocused = true }
    }

    // MARK: Search Bar

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.subheadline)
                .foregroundStyle(Color(.tertiaryLabel))

            TextField("Search for a course", text: $vm.query)
                .font(.body)
                .focused($searchFocused)
                .autocorrectionDisabled()
                .submitLabel(.search)
                .onChange(of: vm.query) { _, _ in vm.queryChanged() }

            if !vm.query.isEmpty {
                Button {
                    vm.query = ""
                    vm.queryChanged()
                    UIImpactFeedbackGenerator(style: .light).impactOccurred()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Color(.tertiaryLabel))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(searchFocused ? Color.forestGreen.opacity(0.5) : Color.clear, lineWidth: 1.5)
        )
        .animation(.easeInOut(duration: 0.15), value: searchFocused)
    }

    // MARK: Content States

    @ViewBuilder
    private var content: some View {
        if let error = vm.errorMessage {
            stateMessage(
                icon: "exclamationmark.triangle.fill",
                tint: .orange,
                title: "Something went wrong",
                subtitle: error
            )
        } else if vm.isLoading {
            VStack(spacing: 12) {
                ProgressView().tint(Color.forestGreen)
                Text("Searching…")
                    .font(.subheadline)
                    .foregroundStyle(Color(.secondaryLabel))
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if vm.courses.isEmpty {
            if vm.hasSearched {
                stateMessage(
                    icon: "magnifyingglass",
                    tint: Color(.tertiaryLabel),
                    title: "No courses found",
                    subtitle: "Try a different name or spelling."
                )
            } else {
                stateMessage(
                    icon: "flag.fill",
                    tint: Color.forestGreen.opacity(0.4),
                    title: "Find your course",
                    subtitle: "Search by course name to start a new round."
                )
            }
        } else {
            resultsList
        }
    }

    private var resultsList: some View {
        ScrollView {
            LazyVStack(spacing: 10) {
                ForEach(vm.courses) { course in
                    NavigationLink(value: course) {
                        courseRow(course)
                    }
                    .buttonStyle(.plain)
                    .simultaneousGesture(TapGesture().onEnded {
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                        searchFocused = false
                    })
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .scrollDismissesKeyboard(.immediately)
    }

    private func courseRow(_ course: Course) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(course.name)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(Color(.label))
                    .multilineTextAlignment(.leading)

                HStack(spacing: 6) {
                    if !course.location.isEmpty {
                        Text(course.location)
                    }
                    if let holes = course.holesCount {
                        if !course.location.isEmpty {
                            Text("•")
                        }
                        Text("\(holes) holes")
                    }
                }
                .font(.caption)
                .foregroundStyle(Color(.secondaryLabel))
            }

            Spacer(minLength: 8)

            Image(systemName: "chevron.right")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(Color(.tertiaryLabel))
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func stateMessage(icon: String, tint: Color, title: String, subtitle: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 38))
                .foregroundStyle(tint)
            Text(title)
                .font(.headline)
                .foregroundStyle(Color(.label))
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Tee Picker

@Observable
class TeePickerViewModel {
    let course: Course
    var detail: CourseDetail?
    var isLoading = false
    var errorMessage: String?

    init(course: Course) {
        self.course = course
    }

    @MainActor
    func load() async {
        guard detail == nil else { return }
        isLoading = true
        errorMessage = nil
        do {
            detail = try await CourseService.shared.details(courseId: course.id)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct CourseTeePickerView: View {
    let course: Course
    /// Called once the player commits to a course + tee. Hands the selection up
    /// to the round-creation flow.
    let onSelect: (RoundCourseSelection) -> Void

    @State private var vm: TeePickerViewModel

    init(course: Course, onSelect: @escaping (RoundCourseSelection) -> Void) {
        self.course = course
        self.onSelect = onSelect
        _vm = State(initialValue: TeePickerViewModel(course: course))
    }

    var body: some View {
        Group {
            if vm.isLoading {
                VStack(spacing: 12) {
                    ProgressView().tint(Color.forestGreen)
                    Text("Loading tees…")
                        .font(.subheadline)
                        .foregroundStyle(Color(.secondaryLabel))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = vm.errorMessage {
                errorState(error)
            } else if let detail = vm.detail {
                teeList(detail)
            }
        }
        .navigationTitle("Select Tees")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.load() }
    }

    private func teeList(_ detail: CourseDetail) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                courseHeader(detail)

                if detail.tees.isEmpty {
                    Text("No tee information available for this course.")
                        .font(.subheadline)
                        .foregroundStyle(Color(.secondaryLabel))
                        .padding(.top, 8)
                } else {
                    ForEach(groupedTees(detail.tees), id: \.label) { group in
                        VStack(alignment: .leading, spacing: 10) {
                            if !group.label.isEmpty {
                                Text(group.label)
                                    .font(.caption)
                                    .fontWeight(.semibold)
                                    .foregroundStyle(Color(.tertiaryLabel))
                                    .textCase(.uppercase)
                                    .kerning(0.6)
                                    .padding(.horizontal, 4)
                            }
                            ForEach(group.tees) { tee in
                                teeRow(tee, detail: detail)
                            }
                        }
                    }
                }
            }
            .padding(.horizontal)
            .padding(.top, 8)
            .padding(.bottom, 24)
        }
    }

    private func courseHeader(_ detail: CourseDetail) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(detail.name)
                .font(.title3)
                .fontWeight(.bold)
            let loc = [detail.city, detail.state].compactMap { $0?.isEmpty == false ? $0 : nil }.joined(separator: ", ")
            if !loc.isEmpty {
                Text(loc)
                    .font(.subheadline)
                    .foregroundStyle(Color(.secondaryLabel))
            }
        }
    }

    private func teeRow(_ tee: TeeBox, detail: CourseDetail) -> some View {
        Button {
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            onSelect(RoundCourseSelection(
                courseId: detail.id,
                courseName: detail.name,
                city: detail.city,
                state: detail.state,
                tee: tee,
                holes: detail.holes
            ))
        } label: {
            HStack(spacing: 14) {
                Circle()
                    .fill(teeSwatch(tee.teeName))
                    .frame(width: 14, height: 14)
                    .overlay(Circle().stroke(Color(.separator), lineWidth: 0.5))

                VStack(alignment: .leading, spacing: 3) {
                    Text(tee.teeName)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(Color(.label))
                    Text(teeStats(tee))
                        .font(.caption)
                        .foregroundStyle(Color(.secondaryLabel))
                }

                Spacer(minLength: 8)

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(Color(.tertiaryLabel))
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 38))
                .foregroundStyle(.orange)
            Text("Couldn't load tees")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center)
            Button("Try Again") {
                Task { await vm.load() }
            }
            .fontWeight(.semibold)
            .foregroundStyle(Color.forestGreen)
            .padding(.top, 4)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: Tee helpers

    private struct TeeGroup { let label: String; let tees: [TeeBox] }

    /// Groups tees by gender (Men's / Women's) when the backend provides it,
    /// otherwise returns a single unlabeled group.
    private func groupedTees(_ tees: [TeeBox]) -> [TeeGroup] {
        let hasGender = tees.contains { $0.gender != nil }
        guard hasGender else { return [TeeGroup(label: "", tees: tees)] }

        let men = tees.filter { $0.gender?.lowercased() == "male" }
        let women = tees.filter { $0.gender?.lowercased() == "female" }
        let other = tees.filter { ($0.gender?.lowercased() != "male") && ($0.gender?.lowercased() != "female") }

        var groups: [TeeGroup] = []
        if !men.isEmpty   { groups.append(TeeGroup(label: "Men's", tees: men)) }
        if !women.isEmpty { groups.append(TeeGroup(label: "Women's", tees: women)) }
        if !other.isEmpty { groups.append(TeeGroup(label: "Other", tees: other)) }
        return groups
    }

    private func teeStats(_ tee: TeeBox) -> String {
        var parts: [String] = []
        if let length = tee.length { parts.append("\(length) yds") }
        if let par = tee.par { parts.append("Par \(par)") }
        if let rating = tee.rating, let slope = tee.slope {
            parts.append(String(format: "%.1f / %d", rating, slope))
        } else if let rating = tee.rating {
            parts.append(String(format: "%.1f", rating))
        } else if let slope = tee.slope {
            parts.append("Slope \(slope)")
        }
        return parts.joined(separator: "  •  ")
    }

    /// Best-effort color swatch from the tee name.
    private func teeSwatch(_ name: String) -> Color {
        switch name.lowercased() {
        case let n where n.contains("black"): return .black
        case let n where n.contains("blue"):  return .blue
        case let n where n.contains("white"): return Color(.systemGray5)
        case let n where n.contains("red"):   return .red
        case let n where n.contains("gold"):  return Color.champagneGold
        case let n where n.contains("green"): return Color.sageGreen
        case let n where n.contains("silver"), let n where n.contains("gray"), let n where n.contains("grey"):
            return Color(.systemGray3)
        default: return Color.forestGreen
        }
    }
}
