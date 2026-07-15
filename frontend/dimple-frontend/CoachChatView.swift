import SwiftUI

// MARK: - Markdown rendering
//
// Coach answers come back as markdown (**bold** subheads, paragraph breaks).
// SwiftUI's `Text` only auto-parses markdown for string *literals*, not a
// `String` variable, so we build the AttributedString ourselves.
// `.inlineOnlyPreservingWhitespace` keeps newlines/paragraph breaks intact while
// still styling inline syntax (bold/italic/links) — full-syntax parsing would
// collapse the whitespace and drop the paragraph structure.
func coachMarkdown(_ string: String) -> AttributedString {
    (try? AttributedString(
        markdown: string,
        options: AttributedString.MarkdownParsingOptions(
            interpretedSyntax: .inlineOnlyPreservingWhitespace
        )
    )) ?? AttributedString(string)
}

// MARK: - View Model

@Observable
final class CoachChatViewModel {
    var messages: [ChatMessage] = []
    var input: String = ""
    var isSending: Bool = false        // waiting on a coach reply
    var isLoadingHistory: Bool = false // fetching an existing thread
    var historyError: String?

    private(set) var conversationID: Int?
    private let roundID: Int?
    private var failedText: String?

    /// - Parameters:
    ///   - conversationID: existing thread to resume, or `nil` for a new chat.
    ///   - roundID: links a *new* conversation to a specific round for context.
    init(conversationID: Int? = nil, roundID: Int? = nil) {
        self.conversationID = conversationID
        self.roundID = roundID
    }

    var isNewEmptyChat: Bool {
        conversationID == nil && messages.isEmpty && !isSending
    }

    // MARK: History

    @MainActor
    func loadHistoryIfNeeded() async {
        guard let id = conversationID, messages.isEmpty, !isLoadingHistory else { return }
        isLoadingHistory = true
        historyError = nil
        do {
            let history = try await CoachService.shared.fetchMessages(conversationID: id)
            withAnimation(.easeInOut(duration: 0.2)) {
                messages = history
                isLoadingHistory = false
            }
        } catch {
            isLoadingHistory = false
            historyError = error.localizedDescription
        }
    }

    // MARK: Sending

    func submit() {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isSending else { return }
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        input = ""
        messages.append(ChatMessage(role: .user, content: trimmed))
        sendToCoach(trimmed)
    }

    /// Fill the composer with a suggested prompt and send it immediately.
    func sendSuggested(_ text: String) {
        input = text
        submit()
    }

    func retry() {
        guard let text = failedText else { return }
        removeTrailingError()
        sendToCoach(text)
    }

    private func sendToCoach(_ text: String) {
        removeTrailingError()
        isSending = true
        failedText = nil

        Task { @MainActor in
            do {
                let resp = try await CoachService.shared.send(
                    message: text,
                    conversationID: conversationID,
                    roundID: roundID
                )
                conversationID = resp.conversation_id
                withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                    messages.append(resp.assistantMessage)
                    isSending = false
                }
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            } catch {
                failedText = text
                withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                    messages.append(ChatMessage(role: .error, content: error.localizedDescription))
                    isSending = false
                }
                UINotificationFeedbackGenerator().notificationOccurred(.error)
            }
        }
    }

    private func removeTrailingError() {
        if messages.last?.role == .error { messages.removeLast() }
    }
}

// MARK: - Chat View

private let suggestedPrompts = [
    "How can I improve?",
    "Where am I losing strokes?",
    "How's my putting?",
    "What should I practice this week?",
]

struct CoachChatView: View {
    @State var vm: CoachChatViewModel
    var navTitle: String = "Dimple Coach"

    @FocusState private var inputFocused: Bool

    init(conversationID: Int? = nil, roundID: Int? = nil, navTitle: String = "Dimple Coach") {
        _vm = State(wrappedValue: CoachChatViewModel(conversationID: conversationID, roundID: roundID))
        self.navTitle = navTitle
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 16) {
                    if vm.isLoadingHistory {
                        historyLoading
                    } else if let e = vm.historyError {
                        historyErrorView(e)
                    } else if vm.isNewEmptyChat {
                        idleState
                    }

                    ForEach(vm.messages) { message in
                        bubble(for: message)
                            .id(message.id)
                    }

                    if vm.isSending {
                        typingBubble.id(bottomAnchorID)
                    } else {
                        Color.clear.frame(height: 1).id(bottomAnchorID)
                    }
                }
                .padding(.horizontal)
                .padding(.top, 12)
                .padding(.bottom, 12)
            }
            .onChange(of: vm.messages.count) { _, _ in scrollToBottom(proxy) }
            .onChange(of: vm.isSending) { _, _ in scrollToBottom(proxy) }
            .onAppear { scrollToBottom(proxy, animated: false) }
        }
        .safeAreaInset(edge: .bottom) {
            inputBar.background(.ultraThinMaterial)
        }
        .navigationTitle(navTitle)
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.loadHistoryIfNeeded() }
    }

    private let bottomAnchorID = "chat-bottom-anchor"

    private func scrollToBottom(_ proxy: ScrollViewProxy, animated: Bool = true) {
        guard !vm.messages.isEmpty || vm.isSending else { return }
        if animated {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
                proxy.scrollTo(bottomAnchorID, anchor: .bottom)
            }
        } else {
            proxy.scrollTo(bottomAnchorID, anchor: .bottom)
        }
    }

    // MARK: Bubble dispatch

    @ViewBuilder
    private func bubble(for message: ChatMessage) -> some View {
        switch message.role {
        case .user:      userBubble(message.content)
        case .assistant: assistantBubble(message)
        case .error:     errorBubble(message.content)
        }
    }

    // MARK: User bubble

    private func userBubble(_ text: String) -> some View {
        HStack {
            Spacer(minLength: 44)
            Text(text)
                .font(.body)
                .foregroundStyle(.white)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color.forestGreen)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("You said: \(text)")
    }

    // MARK: Assistant bubble

    private func assistantBubble(_ message: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: 8) {
            coachAvatar
            VStack(alignment: .leading, spacing: 12) {
                if let c = message.confidence {
                    confidenceIndicator(c)
                }
                Text(coachMarkdown(message.content))
                    .font(.body)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)

                if !message.insights.isEmpty {
                    insightsBlock(message.insights)
                }
                if !message.drills.isEmpty {
                    ForEach(message.drills) { drill in
                        DrillCard(drill: drill)
                    }
                }
            }
            .padding(14)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

            Spacer(minLength: 24)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(assistantA11yLabel(message))
    }

    private func assistantA11yLabel(_ message: ChatMessage) -> String {
        var parts = ["Coach said: \(message.content)"]
        if !message.insights.isEmpty {
            parts.append("Key insights: " + message.insights.joined(separator: ". "))
        }
        if !message.drills.isEmpty {
            parts.append("Recommended drills: " + message.drills.map(\.drill_name).joined(separator: ", "))
        }
        return parts.joined(separator: ". ")
    }

    private var coachAvatar: some View {
        Circle()
            .fill(Color.sageGreen.opacity(0.15))
            .frame(width: 30, height: 30)
            .overlay {
                Image(systemName: "figure.golf")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.forestGreen)
            }
            .accessibilityHidden(true)
    }

    // MARK: Error bubble

    private func errorBubble(_ message: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            coachAvatar
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    Text("Couldn't reach the coach.")
                        .font(.subheadline).fontWeight(.medium)
                }
                Text(message)
                    .font(.caption)
                    .foregroundStyle(Color(.secondaryLabel))
                    .lineLimit(3)
                    .fixedSize(horizontal: false, vertical: true)
                Button {
                    vm.retry()
                } label: {
                    Label("Retry", systemImage: "arrow.clockwise")
                        .font(.subheadline).fontWeight(.semibold)
                        .foregroundStyle(Color.forestGreen)
                }
                .buttonStyle(.plain)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.orange.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(Color.orange.opacity(0.2), lineWidth: 1)
            )
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Coach unavailable: \(message). Double tap Retry to try again.")
    }

    // MARK: Typing indicator

    private var typingBubble: some View {
        HStack(alignment: .top, spacing: 8) {
            coachAvatar
            HStack(spacing: 10) {
                BouncingDots()
                Text("Analyzing your game…")
                    .font(.subheadline)
                    .foregroundStyle(Color(.secondaryLabel))
            }
            .padding(14)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            Spacer(minLength: 24)
        }
        .accessibilityLabel("Coach is thinking")
    }

    // MARK: Insights

    private func insightsBlock(_ insights: [String]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Key Insights", systemImage: "lightbulb.fill")
                .font(.caption).fontWeight(.semibold)
                .foregroundStyle(Color.champagneGold)
            ForEach(insights, id: \.self) { insight in
                HStack(alignment: .top, spacing: 8) {
                    Circle()
                        .fill(Color.sageGreen.opacity(0.15))
                        .frame(width: 18, height: 18)
                        .overlay {
                            Image(systemName: "checkmark")
                                .font(.system(size: 8, weight: .bold))
                                .foregroundStyle(Color.sageGreen)
                        }
                    Text(coachMarkdown(insight))
                        .font(.subheadline)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(.top, 2)
    }

    // MARK: Confidence

    private func confidenceIndicator(_ value: Int) -> some View {
        HStack(spacing: 8) {
            Text("Confidence")
                .font(.caption2).fontWeight(.semibold)
                .foregroundStyle(Color(.tertiaryLabel))
                .textCase(.uppercase).kerning(0.6)
            HStack(spacing: 4) {
                ForEach(1...5, id: \.self) { i in
                    Capsule()
                        .fill(i <= value ? confidenceColor(value) : Color(.systemFill))
                        .frame(width: 18, height: 5)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Confidence \(value) out of 5")
    }

    private func confidenceColor(_ value: Int) -> Color {
        switch value {
        case 1, 2: return .orange
        case 3:    return .champagneGold
        default:   return .sageGreen
        }
    }

    // MARK: Idle / suggestions (new empty chat)

    private var idleState: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 10) {
                coachAvatar
                Text("Ask me anything about your game.")
                    .font(.system(.title3, design: .rounded)).fontWeight(.semibold)
                    .foregroundStyle(Color(.secondaryLabel))
                    .fixedSize(horizontal: false, vertical: true)
            }
            FlowLayout(spacing: 8) {
                ForEach(suggestedPrompts, id: \.self) { q in
                    Button {
                        vm.sendSuggested(q)
                        inputFocused = false
                    } label: {
                        Text(q)
                            .font(.subheadline).fontWeight(.medium)
                            .padding(.horizontal, 14).padding(.vertical, 8)
                            .background(Color.forestGreen.opacity(0.08))
                            .foregroundStyle(Color.forestGreen)
                            .clipShape(Capsule())
                            .overlay(Capsule().stroke(Color.forestGreen.opacity(0.2), lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding(.vertical, 8)
    }

    // MARK: History loading / error

    private var historyLoading: some View {
        HStack(spacing: 10) {
            ProgressView()
            Text("Loading conversation…")
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    private func historyErrorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 34)).foregroundStyle(.orange)
            Text("Couldn't load this conversation").font(.headline)
            Text(message)
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center).lineLimit(3)
            Button("Try Again") { Task { await vm.loadHistoryIfNeeded() } }
                .fontWeight(.semibold).foregroundStyle(Color.forestGreen)
        }
        .frame(maxWidth: .infinity, minHeight: 240)
        .padding(24)
    }

    // MARK: Input bar

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Message your coach…", text: $vm.input, axis: .vertical)
                .lineLimit(1...4)
                .font(.body)
                .focused($inputFocused)
                .padding(.horizontal, 14).padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))

            let canSend = !vm.input.trimmingCharacters(in: .whitespaces).isEmpty && !vm.isSending
            Button {
                vm.submit()
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
            .accessibilityLabel("Send message")
            .animation(.spring(response: 0.3, dampingFraction: 0.7), value: canSend)
        }
        .padding(.horizontal).padding(.vertical, 10)
    }
}

// MARK: - Drill Card (tappable, expandable)

struct DrillCard: View {
    let drill: DrillRecommendation
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) { expanded.toggle() }
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            } label: {
                HStack(spacing: 12) {
                    Circle()
                        .fill(Color.champagneGold.opacity(0.12))
                        .frame(width: 30, height: 30)
                        .overlay {
                            Text("\(drill.priority)")
                                .font(.system(.footnote, design: .rounded)).fontWeight(.bold)
                                .foregroundStyle(Color.champagneGold)
                        }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(drill.drill_name)
                            .font(.subheadline).fontWeight(.semibold)
                            .foregroundStyle(Color(.label))
                        Text(drill.focus_area)
                            .font(.caption).foregroundStyle(Color(.secondaryLabel))
                    }
                    Spacer(minLength: 4)
                    Image(systemName: "chevron.right")
                        .font(.caption).fontWeight(.semibold)
                        .foregroundStyle(Color(.tertiaryLabel))
                        .rotationEffect(.degrees(expanded ? 90 : 0))
                }
                .padding(12)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            if expanded {
                Divider().padding(.horizontal, 12)
                VStack(alignment: .leading, spacing: 10) {
                    Text(coachMarkdown(drill.instructions))
                        .font(.subheadline).lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "flag.fill")
                            .font(.caption).foregroundStyle(Color.sageGreen).padding(.top, 2)
                        Text(coachMarkdown(drill.expected_outcome))
                            .font(.caption).foregroundStyle(Color(.secondaryLabel))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(12)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color(.tertiarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(expanded ? Color.champagneGold.opacity(0.35) : Color.clear, lineWidth: 1)
        )
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Drill \(drill.priority): \(drill.drill_name), \(drill.focus_area). \(drill.instructions). Goal: \(drill.expected_outcome)")
    }
}

// MARK: - Sheet wrapper
//
// Presents a coach chat modally (used from Round detail + post-submit summary).
// Wraps the chat in its own NavigationStack with a Done button.

struct CoachChatSheet: View {
    var conversationID: Int? = nil
    var roundID: Int? = nil
    var title: String = "Dimple Coach"

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            CoachChatView(conversationID: conversationID, roundID: roundID, navTitle: title)
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Done") { dismiss() }
                            .fontWeight(.semibold)
                            .foregroundStyle(Color.forestGreen)
                    }
                }
        }
    }
}

#Preview {
    NavigationStack {
        CoachChatView()
    }
}
