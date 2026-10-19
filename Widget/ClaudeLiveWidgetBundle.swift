import SwiftUI
import WidgetKit

@main
struct ClaudeLiveWidgetBundle: WidgetBundle {
    init() {
        // コマ送りアニメーション用の特殊フォントを実行時登録する
        FrameAnimation.registerFont()
    }

    var body: some Widget {
        sessionsWidget()
        ClaudeLiveActivityWidget()
    }

    private func sessionsWidget() -> some Widget {
        let widget = if #available(iOS 26.0, *) {
            WidgetBundleBuilder.buildLimitedAvailability(ClaudeLivePushSessionsWidget())
        } else {
            WidgetBundleBuilder.buildLimitedAvailability(ClaudeLiveSessionsWidget())
        }
        return WidgetBundleBuilder.buildOptional(widget)
    }
}
