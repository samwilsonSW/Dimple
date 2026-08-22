import SwiftUI

// MARK: - Route

enum CoachRoute: Hashable {
    case new
    case existing(ConversationSummary)
}

// MARK: - View Model

@Observable
final class ConversationListViewModel {
    enum State {
        case loading
        case empty
        case error(String)
        case loaded([ConversationSummary])
    }

    var state: State = .loading
    private var hasLoaded = false

    @MainActor func appear() async { await fetch(showSkeleton: !hasLoaded) }
    @MainActor func refresh() async { await fetch(showSkeleton: false) }

    @MainActor private func fetch(showSkeleton: Bool) async {
        if showSkeleton { state = .loading }
        do {
            let conversations = try await CoachService.shared.fetchConversations()
            hasLoaded = true
            withAnimation(.easeInOut(duration: 0.2)) {
                state = conversations.isEmpty ? .empty : .loaded(conversations)
            }
        } catch {
            if case .loaded = state, !showSkeleton { return }
            state = .error(error.localizedDescription)
        }
    }
}

// MARK: - Conversation List (Coach tab root)

struct ConversationListView: View {
    @State private var vm = ConversationListViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                switch vm.state {
                case .loading:
                    skeleton
                case .empty:
                    emptyState.frame(maxWidth: .infinity, minHeight: 460)
                case .error(let message):
                    errorState(message).frame(maxWidth: .infinity, minHeight: 460)
                case .loaded(let conversations):
                    list(conversations)
                }
            }
            .refreshable { await vm.refresh() }
            .navigationTitle("Coach")
            .navigationDestination(for: CoachRoute.self) { route in
                switch route {
                case .new:
                    CoachChatView()
                case .existing(let c):
                    CoachChatView(conversationID: c.id, navTitle: c.displayTitle)
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink(value: CoachRoute.new) {
                        Image(systemName: "square.and.pencil")
                            .foregroundStyle(Color.forestGreen)
                    }
                    .accessibilityLabel("New chat")
                }
            }
        }
        .task { await vm.appear() }
    }

    // MARK: List

    private func list(_ conversations: [ConversationSummary]) -> some View {
        LazyVStack(spacing: 12) {
            NavigationLink(value: CoachRoute.new) { newChatButton }
                .buttonStyle(.plain)

            ForEach(conversations) { c in
                NavigationLink(value: CoachRoute.existing(c)) {
                    ConversationCard(conversation: c)
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
    }

    private var newChatButton: some View {
        Label("New Chat", systemImage: "plus.bubble")
            .font(.body).fontWeight(.semibold).foregroundStyle(Color.forestGreen)
            .frame(maxWidth: .infinity).frame(height: 52)
            .background(Color.forestGreen.opacity(0.10))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    // MARK: Empty / Error / Skeleton

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "bubble.left.and.text.bubble.right")
                .font(.system(size: 44)).foregroundStyle(Color.forestGreen.opacity(0.4))
            Text("Talk to your coach").font(.title3).fontWeight(.semibold)
            Text("Ask about your game, your stats, or what to work on next.")
                .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center)
            NavigationLink(value: CoachRoute.new) {
                Label("New Chat", systemImage: "plus.bubble")
                    .font(.body).fontWeight(.semibold).foregroundStyle(.white)
                    .padding(.horizontal, 24).frame(height: 50)
                    .background(Color.forestGreen)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(.plain)
            .padding(.top, 4)
        }
        .padding(32)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: 14) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40)).foregroundStyle(.orange)
            Text("Couldn't load conversations").font(.headline)
            Text(message).font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                .multilineTextAlignment(.center).lineLimit(3)
            Text("Pull down to retry.").font(.caption).foregroundStyle(Color(.tertiaryLabel))
            Button("Try Again") { Task { await vm.refresh() } }
                .fontWeight(.semibold).foregroundStyle(Color.forestGreen).padding(.top, 4)
            NavigationLink(value: CoachRoute.new) {
                Text("Start a new chat")
                    .font(.subheadline).fontWeight(.semibold).foregroundStyle(Color.forestGreen)
            }
        }
        .padding(32)
    }

    private var skeleton: some View {
        LazyVStack(spacing: 12) {
            ForEach(0..<5, id: \.self) { _ in skeletonCard }
        }
        .padding()
    }

    private var skeletonCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            grayBar(180, 18)
            grayBar(230, 14)
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func grayBar(_ w: CGFloat, _ h: CGFloat) -> some View {
        RoundedRectangle(cornerRadius: 5).fill(Color(.systemGray5)).frame(width: w, height: h)
    }
}

// MARK: - Conversation Card

struct ConversationCard: View {
    let conversation: ConversationSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(conversation.displayTitle)
                    .font(.headline).lineLimit(1)
                Spacer(minLength: 8)
                if !conversation.displayDate.isEmpty {
                    Text(conversation.displayDate)
                        .font(.caption).foregroundStyle(Color(.secondaryLabel))
                }
            }
            if let preview = conversation.preview, !preview.isEmpty {
                Text(preview)
                    .font(.subheadline).foregroundStyle(Color(.secondaryLabel))
                    .lineLimit(2)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(alignment: .trailing) {
            Image(systemName: "chevron.right")
                .font(.caption).fontWeight(.semibold).foregroundStyle(Color(.tertiaryLabel))
                .padding(.trailing, 14)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11yLabel)
        .accessibilityHint("Double tap to open conversation")
    }

    private var a11yLabel: String {
        var parts = [conversation.displayTitle]
        if !conversation.displayDate.isEmpty { parts.append(conversation.displayDate) }
        if let p = conversation.preview, !p.isEmpty { parts.append(p) }
        return parts.joined(separator: ", ")
    }
}

#Preview {
    ConversationListView()
}
