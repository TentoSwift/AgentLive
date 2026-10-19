import SwiftUI
import UIKit
import CoreText

/// Match the semantic text sizes used by the surrounding Live Activity labels.
/// ReusableMarquee takes a fixed UIFont, so scale it here using the SwiftUI
/// environment before passing it to both measurement and rendering.
struct ActivityMarqueeText: View {
    private let text: String
    private let weight: UIFont.Weight
    private let isEnabled: Bool
    private let sessionTitle: Bool
    @ScaledMetric private var pointSize: CGFloat

    init(_ text: String, compact: Bool = false, weight: UIFont.Weight = .regular,
         sessionTitle: Bool = false, isEnabled: Bool = true) {
        self.text = text
        self.weight = weight
        self.isEnabled = isEnabled
        self.sessionTitle = sessionTitle
        _pointSize = ScaledMetric(wrappedValue: compact ? 11 : 13,
                                 relativeTo: compact ? .caption2 : .footnote)
    }

    var body: some View {
        MarqueeText(text, font: sessionTitle ? SessionTitleFont.uiFont(ofSize: pointSize)
                                           : .systemFont(ofSize: pointSize, weight: weight), isEnabled: isEnabled)
    }
}

/// Completed replies keep their readable prefix and scroll only the hidden suffix.
/// Layout is synchronous: WidgetKit doesn't need geometry callbacks or timers.
struct CompletedResponseView: View {
    let text: String
    var lineLimit: Int? = nil
    var basePointSize: CGFloat = 13
    var isAnimationEnabled: Bool = true
    @ScaledMetric(relativeTo: .footnote) private var scale: CGFloat = 1

    var body: some View {
        let font = UIFont.systemFont(ofSize: basePointSize * scale)
        let plain = Self.displayText(text)
        CompletedResponseLayout(text: plain, font: font, lineLimit: lineLimit) {
            GeometryReader { geometry in
                let parts = ResponseTextPartition(text: plain, font: font,
                    width: geometry.size.width, height: geometry.size.height, lineLimit: lineLimit)
                VStack(alignment: .leading, spacing: parts.overflow.isEmpty ? 0 : 3) {
                    if !parts.prefix.isEmpty {
                        Text(verbatim: parts.prefix)
                            .font(Font(font))
                            .lineLimit(parts.prefixLines)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if !parts.overflow.isEmpty {
                        MarqueeText(parts.overflow, font: font, isEnabled: isAnimationEnabled,
                                    repeatCount: 2, scrollWhenFits: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(verbatim: plain))
    }

    static func displayText(_ text: String) -> String {
        // Keep every table cell, including rows that the compact grid would hide.
        let readable = MarkdownTable.segments(text).map { segment in
            switch segment {
            case .text(let body): return body
            case .table(let table):
                return ([table.headers.joined(separator: " ・ ")]
                    + table.rows.map { $0.joined(separator: " ・ ") }).joined(separator: "\n")
            }
        }.joined(separator: "\n")
        return String(styledMarkdown(readable).characters)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

private struct CompletedResponseLayout: Layout {
    let text: String
    let font: UIFont
    let lineLimit: Int?

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let proposedWidth = proposal.width ?? 280
        let width = proposedWidth.isFinite ? max(1, proposedWidth) : 280
        let parts = ResponseTextPartition(text: text, font: font, width: width,
                                          height: proposal.height, lineLimit: lineLimit)
        return CGSize(width: width, height: parts.height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        for subview in subviews {
            subview.place(at: bounds.origin, anchor: .topLeading,
                          proposal: ProposedViewSize(width: bounds.width, height: bounds.height))
        }
    }
}

// MARK: - Measured response overflow

struct ResponseTextPartition {
    let prefix: String
    let overflow: String
    let prefixLines: Int
    let height: CGFloat

    init(text: String, font: UIFont, width: CGFloat, height: CGFloat? = nil, lineLimit: Int? = nil) {
        let value = text as NSString
        let viewportWidth = width.isFinite ? max(1, width) : 280
        let typesetter = CTTypesetterCreateWithAttributedString(
            NSAttributedString(string: text, attributes: [.font: font]))
        var ends: [Int] = []
        var offset = 0
        while offset < value.length {
            let count = CTTypesetterSuggestLineBreak(typesetter, offset, Double(viewportWidth))
            // A viewport narrower than a single emoji must still advance at a
            // composed character boundary, without dropping or splitting it.
            offset += count > 0 ? count : value.rangeOfComposedCharacterSequence(at: offset).length
            ends.append(offset)
        }
        let lineHeight = ceil(font.lineHeight)
        var budget = max(1, min(ends.count, lineLimit ?? ends.count))
        if let height, height.isFinite {
            let fitsAll = ends.count <= budget && CGFloat(ends.count) * lineHeight <= height + 0.5
            if !fitsAll {
                // Only reserve a marquee row when the full reply truly does
                // not fit. Use every remaining complete line for static text.
                let rows = floor(max(0, height + 0.5 - 3) / lineHeight)
                budget = min(budget, max(1, Int(min(rows, CGFloat(Int.max / 2)))))
            }
        }
        if ends.count <= budget {
            prefix = text
            overflow = ""
            prefixLines = ends.count
            self.height = CGFloat(ends.count) * lineHeight
        } else {
            prefixLines = budget - 1
            let cut = prefixLines > 0 ? ends[prefixLines - 1] : 0
            prefix = value.substring(to: cut).trimmingCharacters(in: .whitespacesAndNewlines)
            overflow = value.substring(from: cut).trimmingCharacters(in: .whitespacesAndNewlines)
            self.height = CGFloat(budget) * lineHeight + (prefixLines > 0 ? 3 : 0)
        }
    }
}

struct SessionUsageView: View {
    var tokenCount: Int?
    var weeklyUsedPercent: Double?
    var font: Font = .caption2

    var body: some View {
        if let label = sessionUsageText(tokenCount: tokenCount, weeklyUsedPercent: weeklyUsedPercent) {
            Text(label)
                .font(font)
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityLabel(Text("今回の作業のトークン数、週間はアカウント全体の使用率。\(label)"))
        }
    }
}

/// Marks the response (or a session row) as the part allowed to use spare height.
struct ResponseContentKey: LayoutValueKey {
    static let defaultValue = false
}

/// A vertical stack which measures fixed labels first and gives the reply all
/// remaining height. No asynchronous geometry state is needed in WidgetKit.
struct ReplyPriorityLayout: Layout {
    var maxHeight: CGFloat? = nil
    var spacing: CGFloat = 6

    private func measurements(width: CGFloat, height: CGFloat?, subviews: Subviews) -> [CGSize] {
        let natural = subviews.map { $0.sizeThatFits(ProposedViewSize(width: width, height: nil)) }
        let flexible = subviews.indices.filter { subviews[$0][ResponseContentKey.self] }
        let limits = [height, maxHeight].compactMap { $0 }.filter { $0.isFinite && $0 >= 0 }
        guard let limit = limits.min(), !flexible.isEmpty else { return natural }
        let visibleCount = natural.filter { $0.height > 0 }.count
        let gaps = CGFloat(max(0, visibleCount - 1)) * spacing
        let fixed = subviews.indices.filter { !subviews[$0][ResponseContentKey.self] }
            .reduce(CGFloat.zero) { $0 + natural[$1].height }
        let allocations = ResponseSpaceAllocation.heights(
            ideal: flexible.map { natural[$0].height }, available: max(0, limit - fixed - gaps))
        var sizes = natural
        for (index, allocated) in zip(flexible, allocations) {
            sizes[index] = subviews[index].sizeThatFits(ProposedViewSize(width: width, height: allocated))
        }
        return sizes
    }

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width.flatMap { $0.isFinite ? max(1, $0) : nil } ?? 280
        let sizes = measurements(width: width, height: proposal.height, subviews: subviews)
        let gaps = CGFloat(max(0, sizes.filter { $0.height > 0 }.count - 1)) * spacing
        return CGSize(width: width, height: sizes.reduce(CGFloat.zero) { $0 + $1.height } + gaps)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let sizes = measurements(width: bounds.width, height: bounds.height, subviews: subviews)
        var y = bounds.minY
        var needsGap = false
        for (subview, size) in zip(subviews, sizes) {
            if size.height > 0, needsGap { y += spacing }
            subview.place(at: CGPoint(x: bounds.minX, y: y), anchor: .topLeading,
                          proposal: ProposedViewSize(width: bounds.width, height: size.height))
            if size.height > 0 { y += size.height; needsGap = true }
        }
    }
}

/// Fair sharing reassigns unused space from short sessions to longer replies.
enum ResponseSpaceAllocation {
    static func heights(ideal: [CGFloat], available: CGFloat) -> [CGFloat] {
        var result = Array(repeating: CGFloat.zero, count: ideal.count)
        var remaining = max(0, available)
        let order = ideal.indices.sorted { ideal[$0] < ideal[$1] }
        for (position, index) in order.enumerated() {
            let share = remaining / CGFloat(order.count - position)
            result[index] = min(max(0, ideal[index]), share)
            remaining -= result[index]
        }
        return result
    }
}
