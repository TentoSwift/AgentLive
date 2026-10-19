// Declarations recovered from the iOS 27.2 arm64 Simulator runtime.
// Append to the matching local SDK's SwiftUICore.swiftinterface; do not compile
// this file as ordinary app source or define a replacement implementation.
// SwiftUICore's module ABI name must remain SwiftUI.

public enum AppearanceAnimationStrategy {
  case withAnimation
  case animationValue
}

extension SwiftUICore.View {
  nonisolated public func appearanceAnimation<Content>(
    animation: SwiftUICore.Animation,
    strategy: SwiftUICore.AppearanceAnimationStrategy,
    modifier: (Self, Swift.Bool) -> Content
  ) -> some SwiftUICore.View where Content : SwiftUICore.View
}
