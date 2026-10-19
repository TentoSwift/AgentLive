import SwiftUI
import UIKit

/// A single-line, physically leftward marquee for WidgetKit and ActivityKit.
///
/// Set PRIVATE_MARQUEE_ENABLED and build the supplied SwiftUICore bridge to
/// enable animation. Without that compilation condition this is static Text
/// and does not reference the private animation API.
///
/// Specify typography through `font`. External bold/italic/kerning/tracking
/// modifiers are unsupported because they can invalidate width measurement.
/// The supplied UIFont has a fixed point size. Pass a scaled font if needed.
/// The parent must propose a finite width; do not apply horizontal fixedSize.
public struct MarqueeText: View {
    private let text: String
    private let font: UIFont
    private let speed: CGFloat
    private let spacing: CGFloat
    private let isEnabled: Bool
    private let respectsReduceMotion: Bool
    private let repeatCount: Int?
    private let scrollWhenFits: Bool

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.layoutDirection) private var layoutDirection

    /// - Parameters:
    ///   - text: Plain text; line breaks and tabs are displayed as spaces.
    ///   - font: Used for both synchronous measurement and SwiftUI rendering.
    ///   - speed: Points per second. Nonpositive/nonfinite values stop scrolling.
    ///   - spacing: Gap between copies. Negative/nonfinite values become zero.
    ///   - isEnabled: Disables movement while retaining a truncated static label.
    ///   - respectsReduceMotion: Stops when the environment requests reduced motion.
    public init(
        _ text: String,
        font: UIFont = .systemFont(ofSize: 17),
        speed: CGFloat = 40,
        spacing: CGFloat = 32,
        isEnabled: Bool = true,
        respectsReduceMotion: Bool = true,
        repeatCount: Int? = nil,
        scrollWhenFits: Bool = false
    ) {
        self.text = text
        self.font = font
        self.speed = speed
        self.spacing = spacing
        self.isEnabled = isEnabled
        self.respectsReduceMotion = respectsReduceMotion
        self.repeatCount = repeatCount.map { min(10, max(1, $0)) }
        self.scrollWhenFits = scrollWhenFits
    }

    public var body: some View {
        let normalized = Self.singleLine(text)
        let measured = (normalized as NSString).size(withAttributes: [.font: font])
        let metrics = MarqueeMetrics(
            measuredSize: measured,
            lineHeight: font.lineHeight,
            spacing: spacing,
            speed: speed
        )

        GeometryReader { geometry in
            let width = MarqueeMetrics.finiteNonnegative(geometry.size.width)
            let step = scrollWhenFits ? max(metrics.step, width + metrics.spacing) : metrics.step
            let duration = metrics.duration > 0 ? Double(step / speed) : 0
            Group {
                #if PRIVATE_MARQUEE_ENABLED
                if metrics.shouldAnimate(
                    viewportWidth: width,
                    isEnabled: isEnabled && !normalized.isEmpty,
                    reduceMotion: respectsReduceMotion && reduceMotion,
                    scrollWhenFits: scrollWhenFits
                ) {
                    HStack(spacing: step - metrics.contentWidth) {
                        copy(normalized, metrics: metrics)
                        copy(normalized, metrics: metrics)
                    }
                    .fixedSize()
                    .appearanceAnimation(
                        animation: animation(duration: duration),
                        strategy: .withAnimation
                    ) { view, active in
                        view.offset(x: active ? -step : 0)
                    }
                    // The private renderer can retain the old repeating period
                    // after an input update. Recreate it when geometry changes.
                    .id(MarqueeAnimationIdentity(
                        text: normalized,
                        font: font,
                        step: step,
                        height: metrics.height,
                        duration: duration,
                        viewportWidth: width,
                        rightToLeft: layoutDirection == .rightToLeft,
                        repeatCount: repeatCount
                    ))
                    // Physical copy order stays left-to-right. Each Text still
                    // receives the caller's direction for Unicode/bidi shaping.
                    .frame(width: width, height: metrics.height, alignment: .leading)
                    .environment(\.layoutDirection, .leftToRight)
                } else {
                    staticLabel(normalized)
                }
                #else
                staticLabel(normalized)
                #endif
            }
            .frame(width: width, height: metrics.height, alignment: .leading)
            .clipped()
        }
        .frame(height: metrics.height)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(verbatim: text))
        .accessibilityAddTraits(.isStaticText)
    }

    private func animation(duration: Double) -> Animation {
        if let repeatCount {
            return .linear(duration: duration).repeatCount(repeatCount, autoreverses: false).delay(1)
        }
        return .linear(duration: duration).repeatForever(autoreverses: false)
    }

    private func staticLabel(_ value: String) -> some View {
        Text(verbatim: value)
            .font(Font(font))
            .lineLimit(1)
            .truncationMode(.tail)
            .textCase(nil)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func copy(_ value: String, metrics: MarqueeMetrics) -> some View {
        Text(verbatim: value)
            .font(Font(font))
            .lineLimit(1)
            .textCase(nil)
            .fixedSize(horizontal: true, vertical: true)
            .environment(\.layoutDirection, layoutDirection)
            .frame(width: metrics.contentWidth, height: metrics.height, alignment: .leading)
    }

    static func singleLine(_ value: String) -> String {
        value.replacingOccurrences(of: "\r\n", with: " ")
            .components(separatedBy: .newlines).joined(separator: " ")
            .replacingOccurrences(of: "\t", with: " ")
    }
}

private struct MarqueeAnimationIdentity: Hashable {
    let text: String
    let font: UIFont
    let step: CGFloat
    let height: CGFloat
    let duration: Double
    let viewportWidth: CGFloat
    let rightToLeft: Bool
    let repeatCount: Int?
}

/// Pure geometry, shared with the small simulator validation executable.
/// No layout callback, timer, state mutation, or UIView is used for measurement.
struct MarqueeMetrics {
    let contentWidth: CGFloat
    let height: CGFloat
    let spacing: CGFloat
    let step: CGFloat
    let duration: Double

    init(measuredSize: CGSize, lineHeight: CGFloat, spacing: CGFloat, speed: CGFloat) {
        contentWidth = ceil(Self.finiteNonnegative(measuredSize.width))
        height = max(1, ceil(max(Self.finiteNonnegative(measuredSize.height),
                                 Self.finiteNonnegative(lineHeight))))
        self.spacing = Self.finiteNonnegative(spacing)
        step = contentWidth + self.spacing
        let seconds = Double(step / speed)
        duration = speed.isFinite && speed > 0 && seconds.isFinite && seconds > 0
            ? seconds : 0
    }

    func shouldAnimate(viewportWidth: CGFloat, isEnabled: Bool, reduceMotion: Bool,
                       scrollWhenFits: Bool = false) -> Bool {
        isEnabled && !reduceMotion && viewportWidth.isFinite && viewportWidth > 0
            && (contentWidth > viewportWidth || scrollWhenFits) && step.isFinite && duration > 0
    }

    static func finiteNonnegative(_ value: CGFloat) -> CGFloat {
        value.isFinite && value > 0 ? value : 0
    }
}
