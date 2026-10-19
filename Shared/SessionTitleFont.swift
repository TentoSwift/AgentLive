import SwiftUI
import CoreText
#if canImport(UIKit)
import UIKit
#endif

/// Personal preview typography shared by every session-title surface.
/// The font and its notice are excluded from Release products.
enum SessionTitleFont {
    static let postScriptName = "MacintoshSkeletalFilled-Regular"

    static let isAvailable: Bool = {
        #if DEBUG
        guard let url = Bundle.main.url(forResource: "MacintoshSkeletalFilled", withExtension: "otf") else { return false }
        _ = CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        return (CTFontManagerCopyAvailablePostScriptNames() as? [String])?.contains(postScriptName) == true
        #else
        return false
        #endif
    }()

    static func font(ofSize size: CGFloat) -> Font {
        isAvailable ? .custom(postScriptName, fixedSize: size) : .system(size: size, weight: .semibold)
    }

    #if canImport(UIKit)
    static func uiFont(ofSize size: CGFloat) -> UIFont {
        if isAvailable, let font = UIFont(name: postScriptName, size: size) { return font }
        return .systemFont(ofSize: size, weight: .semibold)
    }
    #endif
}

struct SessionTitleText: View {
    let text: String
    var size: CGFloat = 17
    @ScaledMetric(relativeTo: .headline) private var scale: CGFloat = 1

    init(_ text: String, size: CGFloat = 17) { self.text = text; self.size = size }

    var body: some View {
        Text(verbatim: text).font(SessionTitleFont.font(ofSize: size * scale))
    }
}

private struct SessionNavigationTitle: ViewModifier {
    let title: String

    func body(content: Content) -> some View {
        #if os(watchOS)
        // watchOS doesn't support a principal toolbar item. Keep a custom
        // title above the content, outside the scrolling conversation.
        content.navigationTitle("")
            .safeAreaInset(edge: .top, spacing: 2) {
                SessionTitleText(title).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 8)
            }
        #else
        content.navigationTitle(title)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    SessionTitleText(title).lineLimit(1).accessibilityAddTraits(.isHeader)
                }
            }
        #endif
    }
}

extension View {
    func sessionNavigationTitle(_ title: String) -> some View {
        modifier(SessionNavigationTitle(title: title))
    }
}
