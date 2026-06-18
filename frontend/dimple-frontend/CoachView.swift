import SwiftUI

// MARK: - Design Tokens

extension Color {
    static let forestGreen   = Color(red: 30/255,  green: 70/255,  blue: 32/255)
    static let sageGreen     = Color(red: 76/255,  green: 187/255, blue: 23/255)
    static let champagneGold = Color(red: 212/255, green: 175/255, blue: 55/255)
}

// MARK: - View Model

@Observable
class CoachViewModel {
    var question: String    = ""
    var lastQuestion: String = ""
    var response: CoachResponse?
    var isLoading: Bool     = false
    var errorMessage: String?
    var expandedDrill: Int?

    func send() {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isLoading else { return }

        UIImpactFeedbackGenerator(style: .light).impactOccurred()

        lastQuestion = trimmed
        question     = ""
        isLoading    = true
        response     = nil
        errorMessage = nil
        expandedDrill = nil

        Task {
            do {
                let result = try await CoachService.shared.ask(question: trimmed)
                await MainActor.run {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
                        self.response  = result
                        self.isLoading = false
                    }
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                }
            } catch {
                await MainActor.run {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.75)) {
                        self.errorMessage = error.localizedDescription
                        self.isLoading    = false
                    }
                    UINotificationFeedbackGenerator().notificationOccurred(.error)
                }
            }
        }
    }
}

// MARK: - Coach View

private let suggestedQuestions = [
    "What should I work on?",
    "How is my approach play?",
    "Where am I losing the most strokes?",
    "How is my driving?",
    "What drills should I do?",
]

struct CoachView: View {
    @Environment(AuthViewModel.self) private var auth
    @State private var vm = CoachViewModel()
    @FocusState private var inputFocused: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                if !vm.isLoading && vm.response == nil && vm.errorMessage == nil {
                    idleState
                }
                if vm.isLoading    { loadingCard }
                if let e = vm.errorMessage { errorCard(e) }
                if let r = vm.response     { responseCards(r) }
            }
            .padding(.horizontal)
            .padding(.top, 8)
            .padding(.bottom, 20)
        }
        .safeAreaInset(edge: .bottom) {
            inputBar
                .background(.ultraThinMaterial)
        }
        .navigationTitle("Coach")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    if let user = auth.currentUser {
                        Text(user.email ?? user.id)
                            .font(.footnote)
                    }
                    Button(role: .destructive) {
                        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                        auth.signOut()
                    } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                } label: {
                    Image(systemName: "person.circle")
                        .foregroundStyle(Color.forestGreen)
                }
            }
        }
    }

    // MARK: Idle State

    private var idleState: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("What would you like to know?")
                .font(.system(.title3, design: .rounded))
                .fontWeight(.semibold)
                .foregroundStyle(Color(.secondaryLabel))
                .padding(.top, 8)

            FlowLayout(spacing: 8) {
                ForEach(suggestedQuestions, id: \.self) { q in
                    Button {
                        vm.question = q
                        vm.send()
                    } label: {
                        Text(q)
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(Color.forestGreen.opacity(0.08))
                            .foregroundStyle(Color.forestGreen)
                            .clipShape(Capsule())
                            .overlay(Capsule().stroke(Color.forestGreen.opacity(0.2), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    // MARK: Loading Card

    private var loadingCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            questionBubble(vm.lastQuestion)

            HStack(spacing: 10) {
                BouncingDots()
                Text("Analyzing your game…")
                    .font(.subheadline)
                    .foregroundStyle(Color(.secondaryLabel))
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }

    // MARK: Error Card

    private func errorCard(_ message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
            Text(message)
                .font(.subheadline)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.orange.opacity(0.2), lineWidth: 1))
    }

    // MARK: Response Cards

    private func responseCards(_ resp: CoachResponse) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            questionBubble(vm.lastQuestion)
            answerCard(resp)
            if !resp.key_insights.isEmpty         { insightsCard(resp.key_insights) }
            if !resp.drill_recommendations.isEmpty { drillsSection(resp.drill_recommendations) }
        }
    }

    // MARK: Question Echo Bubble

    private func questionBubble(_ text: String) -> some View {
        HStack {
            Spacer()
            Text(text)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(Color(.label))
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color.forestGreen.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .stroke(Color.forestGreen.opacity(0.2), lineWidth: 1)
                )
        }
    }

    // MARK: Answer Card

    private func answerCard(_ resp: CoachResponse) -> some View {
        HStack(alignment: .top, spacing: 0) {
            // Left accent bar
            RoundedRectangle(cornerRadius: 2)
                .fill(Color.sageGreen)
                .frame(width: 3)

            VStack(alignment: .leading, spacing: 14) {
                confidenceIndicator(resp.confidence)
                Text(resp.answer)
                    .font(.body)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(16)
        }
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    // MARK: Confidence Indicator

    private func confidenceIndicator(_ value: Int) -> some View {
        HStack(spacing: 8) {
            Text("Confidence")
                .font(.caption2)
                .fontWeight(.semibold)
                .foregroundStyle(Color(.tertiaryLabel))
                .textCase(.uppercase)
                .kerning(0.6)
            HStack(spacing: 4) {
                ForEach(1...5, id: \.self) { i in
                    Capsule()
                        .fill(i <= value ? confidenceColor(value) : Color(.systemFill))
                        .frame(width: 22, height: 5)
                }
            }
        }
    }

    private func confidenceColor(_ value: Int) -> Color {
        switch value {
        case 1, 2: return .orange
        case 3:    return .champagneGold
        default:   return .sageGreen
        }
    }

    // MARK: Insights Card

    private func insightsCard(_ insights: [String]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Key Insights", systemImage: "lightbulb.fill")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundStyle(Color.champagneGold)

            VStack(alignment: .leading, spacing: 10) {
                ForEach(insights, id: \.self) { insight in
                    HStack(alignment: .top, spacing: 10) {
                        Circle()
                            .fill(Color.sageGreen.opacity(0.15))
                            .frame(width: 20, height: 20)
                            .overlay {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 9, weight: .bold))
                                    .foregroundStyle(Color.sageGreen)
                            }
                        Text(insight)
                            .font(.subheadline)
                            .lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    // MARK: Drills

    private func drillsSection(_ drills: [DrillRecommendation]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Recommended Drills", systemImage: "figure.golf.circle")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundStyle(Color(.secondaryLabel))
                .padding(.horizontal, 4)

            ForEach(drills) { drill in
                drillCard(drill)
            }
        }
    }

    private func drillCard(_ drill: DrillRecommendation) -> some View {
        let isExpanded = vm.expandedDrill == drill.priority

        return VStack(alignment: .leading, spacing: 0) {
            // Header row
            Button {
                withAnimation(.spring(response: 0.35, dampingFraction: 0.75)) {
                    vm.expandedDrill = isExpanded ? nil : drill.priority
                }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                HStack(spacing: 12) {
                    // Priority badge
                    Circle()
                        .fill(Color.champagneGold.opacity(0.12))
                        .frame(width: 32, height: 32)
                        .overlay {
                            Text("\(drill.priority)")
                                .font(.system(.footnote, design: .rounded))
                                .fontWeight(.bold)
                                .foregroundStyle(Color.champagneGold)
                        }

                    VStack(alignment: .leading, spacing: 2) {
                        Text(drill.drill_name)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundStyle(Color(.label))
                        Text(drill.focus_area)
                            .font(.caption)
                            .foregroundStyle(Color(.secondaryLabel))
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(Color(.tertiaryLabel))
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                }
                .padding(14)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            // Expanded detail
            if isExpanded {
                Divider().padding(.horizontal, 14)

                VStack(alignment: .leading, spacing: 12) {
                    Text(drill.instructions)
                        .font(.subheadline)
                        .lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)

                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "flag.fill")
                            .font(.caption)
                            .foregroundStyle(Color.sageGreen)
                            .padding(.top, 2)
                        Text(drill.expected_outcome)
                            .font(.caption)
                            .foregroundStyle(Color(.secondaryLabel))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.top, 2)
                }
                .padding(14)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(
                    isExpanded ? Color.champagneGold.opacity(0.35) : Color.clear,
                    lineWidth: 1
                )
        )
        .animation(.spring(response: 0.35, dampingFraction: 0.75), value: isExpanded)
    }

    // MARK: Input Bar

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Ask your coach…", text: $vm.question, axis: .vertical)
                .lineLimit(1...4)
                .font(.body)
                .focused($inputFocused)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                .onSubmit { vm.send() }

            let canSend = !vm.question.trimmingCharacters(in: .whitespaces).isEmpty && !vm.isLoading
            Button {
                vm.send()
                inputFocused = false
            } label: {
                Circle()
                    .fill(canSend ? Color.forestGreen : Color(.systemFill))
                    .frame(width: 42, height: 42)
                    .overlay {
                        Image(systemName: "arrow.up")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(canSend ? .white : Color(.tertiaryLabel))
                    }
            }
            .disabled(!canSend)
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: canSend)
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
    }
}

// MARK: - Bouncing Dots

struct BouncingDots: View {
    @State private var animating = false

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3, id: \.self) { i in
                Circle()
                    .fill(Color.sageGreen)
                    .frame(width: 7, height: 7)
                    .offset(y: animating ? -5 : 0)
                    .animation(
                        .easeInOut(duration: 0.4)
                            .repeatForever(autoreverses: true)
                            .delay(Double(i) * 0.14),
                        value: animating
                    )
            }
        }
        .onAppear { animating = true }
    }
}

// MARK: - Flow Layout (wrapping chip grid)

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        layout(for: subviews, maxWidth: proposal.width ?? 0).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = layout(for: subviews, maxWidth: bounds.width)
        for (index, frame) in result.frames.enumerated() {
            subviews[index].place(
                at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY),
                proposal: .unspecified
            )
        }
    }

    private func layout(for subviews: Subviews, maxWidth: CGFloat) -> (size: CGSize, frames: [CGRect]) {
        var frames: [CGRect] = []
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0; y += rowHeight + spacing; rowHeight = 0
            }
            frames.append(CGRect(origin: CGPoint(x: x, y: y), size: size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return (CGSize(width: maxWidth, height: y + rowHeight), frames)
    }
}

#Preview {
    NavigationStack {
        CoachView()
    }
}
