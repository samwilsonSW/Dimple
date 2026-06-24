import SwiftUI

/// Owns the new-round flow: course search → tee picker → handoff.
/// The handoff currently lands on a confirmation placeholder; the Scorecard
/// Entry View (next [CC] task) will replace that destination and consume the
/// `RoundCourseSelection` (course_id + tee + hole template).
struct NewRoundView: View {
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            CourseSearchView()
                .navigationDestination(for: Course.self) { course in
                    CourseTeePickerView(course: course) { selection in
                        path.append(selection)
                    }
                }
                .navigationDestination(for: RoundCourseSelection.self) { selection in
                    RoundSelectionConfirmationView(selection: selection) {
                        path = NavigationPath()
                    }
                }
        }
    }
}

// MARK: - Selection Confirmation (placeholder for Scorecard Entry View)

struct RoundSelectionConfirmationView: View {
    let selection: RoundCourseSelection
    let onStartOver: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.title2)
                        .foregroundStyle(Color.sageGreen)
                    Text("Course Selected")
                        .font(.title3)
                        .fontWeight(.bold)
                }

                card {
                    detailRow("Course", selection.courseName)
                    if !selection.location.isEmpty {
                        Divider()
                        detailRow("Location", selection.location)
                    }
                    Divider()
                    detailRow("Tee", selection.tee.teeName)
                    Divider()
                    detailRow("Course ID", selection.courseId, mono: true)
                    Divider()
                    detailRow("Holes loaded", "\(selection.holes.count)")
                }

                Text("This is a placeholder. The Scorecard Entry View will take this selection and post the round.")
                    .font(.footnote)
                    .foregroundStyle(Color(.secondaryLabel))

                Button(action: onStartOver) {
                    Text("Start Over")
                        .font(.body)
                        .fontWeight(.semibold)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .background(Color.forestGreen)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
                .buttonStyle(.plain)
            }
            .padding()
        }
        .navigationTitle("Confirm")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            content()
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func detailRow(_ label: String, _ value: String, mono: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .font(.caption)
                .foregroundStyle(Color(.secondaryLabel))
            Spacer(minLength: 12)
            Text(value)
                .font(mono ? .system(.subheadline, design: .monospaced) : .subheadline)
                .fontWeight(.medium)
                .multilineTextAlignment(.trailing)
        }
    }
}
