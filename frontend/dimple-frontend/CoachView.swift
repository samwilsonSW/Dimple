import SwiftUI

// Shared design primitives for the app. The conversational coach lives in
// `CoachChatView` / `ConversationListView`; this file now holds only the tokens
// and small reusable views that the rest of the UI depends on.

// MARK: - Design Tokens

extension Color {
    static let forestGreen   = Color(red: 30/255,  green: 70/255,  blue: 32/255)
    static let sageGreen     = Color(red: 76/255,  green: 187/255, blue: 23/255)
    static let champagneGold = Color(red: 212/255, green: 175/255, blue: 55/255)
}

// MARK: - Bouncing Dots (coach "typing" indicator)

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
