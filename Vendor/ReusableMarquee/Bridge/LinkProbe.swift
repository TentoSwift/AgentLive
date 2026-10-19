import SwiftUI

// Build-time only. This dylib must not be embedded in an app.
public func privateMarqueeBridgeLinkProbe() -> some View {
    Text("Bridge link probe")
        .appearanceAnimation(
            animation: .linear(duration: 6).repeatForever(autoreverses: false),
            strategy: .withAnimation
        ) { view, active in
            view.offset(x: active ? -300 : 0)
        }
}
