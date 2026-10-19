import ActivityKit
import SwiftUI
import UIKit
import CoreText
import WidgetKit

/// ツール名に対応する SF Symbol 名。
/// デーモン側のツールログ（"SFSymbol名|本文"）と同じ対応表にしてある
func toolSymbolName(_ tool: String) -> String {
    switch tool {
    case "Bash":                        return "terminal"
    case "Read":                        return "doc.text"
    case "Edit", "Write", "NotebookEdit": return "pencil"
    case "Grep", "Glob":                return "magnifyingglass"
    case "Task", "Agent":               return "rectangle.stack.fill"
    case "WebFetch", "WebSearch":       return "globe"
    default:                            return "wrench.and.screwdriver"
    }
}

/// 実行中ツールのアイコン。Task/Agent（サブエージェント）はカスタムシンボル
/// （Assets.xcassets の ClaudeTaskRunning）、それ以外は toolSymbolName の SF Symbol
@ViewBuilder
func toolRunningIcon(_ tool: String, provider: SessionProvider = .claude) -> some View {
    if tool == "Task" || tool == "Agent" {
        Image("\(provider.symbolPrefix)TaskRunning")
            .renderingMode(.template)
            .resizable()
            .scaledToFit()
    } else {
        Image(systemName: toolSymbolName(tool))
            .resizable()
            .scaledToFit()
    }
}

/// 完了時、直近に使ったツールのチェックマーク付きカスタムシンボル名。
/// Assets.xcassets に "Claude<ツール名>Checkmark" という名前の .symbolset を
/// 追加すれば自動的に使われる（例: ClaudeBashCheckmark）。
/// まだ用意していないツールは nil を返し、呼び出し側は共通の
/// ClaudeBadgeCheckmark にフォールバックする
func toolCheckmarkSymbolName(_ tool: String, provider: SessionProvider = .claude) -> String? {
    // toolSymbolName と同じグループ分けで、似たツールは1つのシンボルを共有する
    let group: String
    switch tool {
    case "Bash":                          group = "Bash"
    case "Read":                          group = "Read"
    case "Edit", "Write", "NotebookEdit": group = "Edit"
    case "Grep", "Glob":                  group = "Grep"
    case "Task", "Agent":                 group = "Task"
    case "WebFetch", "WebSearch":         group = "WebFetch"
    default:                              return nil
    }
    let name = "\(provider.symbolPrefix)\(group)Checkmark"
    return UIImage(named: name) != nil ? name : nil
}

/// インライン Markdown（**強調**・`コード` など）を解釈する
func styledMarkdown(_ text: String) -> AttributedString {
    (try? AttributedString(
        markdown: text,
        options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
        ?? AttributedString(text)
}

struct ClaudeLiveActivityWidget: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: ClaudeActivityAttributes.self) { context in
            // ロック画面 / 通知バナー
            // watchOS の Smart Stack はカード側が背景を持つため、ここでは
            // 黒背景を付けず LockScreenView 側で iOS のときだけ付ける
            LockScreenView(context: context)
                .activitySystemActionForegroundColor(.white)
                // タップでアプリを開き、セッション詳細へ直接遷移させる。
                // ライブアクティビティは Button(intent:)・Link・widgetURL の
                // いずれを使っても自アプリ以外は開けない（実機で確認済み）ため、
                // 外部アプリ（ショートカット）への直接遷移は諦め、
                // 確実に動く「アプリを開く」方式に統一する
                .widgetURL(URL(string: "claudelive://session/\(context.attributes.sessionId)"))
        } dynamicIsland: { context in
            let status = ClaudeStatus(context.state.status)
            let provider = context.state.sessionProvider
            // 完了時、返答が長くて場所を取るなら他の情報（プロジェクト名・状態ラベル等）は省く
            let expandResponse = status == .done && context.state.lastResponse.count >= 100
            return DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    HStack(spacing: 6) {
                        StatusIconView(status: status, provider: provider, size: 24)
                        if status != .question && status != .done {
                            Text(status.label)
                                .font(.caption2)
                                .foregroundStyle(status.color(for: provider))
                                .lineLimit(1)
                        }
                    }
                    .padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    // 質問中は経過時間よりも質問カードの横幅を優先する。
                    // DI では経過時間は表示しない（ロック画面側にはある）
                    if status != .question, !context.state.model.isEmpty {
                        Text(shortModelName(context.state.model))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .frame(maxWidth: 100)
                            .padding(.trailing, 4)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    ReplyPriorityLayout(maxHeight: 120, spacing: 3) {
                        if !context.state.question.isEmpty {
                            QuestionView(sessionId: context.attributes.sessionId,
                                         question: context.state.question,
                                         options: context.state.options,
                                         tint: status.color(for: provider),
                                         compact: true,
                                         isSettled: context.state.textSettled,
                              questionCount: context.state.questionCount)
                        } else {
                            // バックグラウンドタスクの進捗。ツールログや返答表示の邪魔にならない
                            // 控えめな 1 行として最上部に添える
                            if (context.state.taskTotal ?? 0) > 0 {
                                TaskProgressLine(done: context.state.taskDone ?? 0,
                                                  total: context.state.taskTotal ?? 0,
                                                  active: context.state.taskActive ?? "")
                            }
                            // 完了時、返答が長くて場所を取るならツールログは省いて
                            // 返答を複数行で優先表示する（マーキーは1行しか流せないため）
                            if expandResponse {
                                if !context.state.lastPrompt.isEmpty {
                                    HStack(alignment: .center, spacing: 6) {
                                        PromptIcon(size: 24, color: .secondary)
                                        ActivityMarqueeText(context.state.lastPrompt)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                HStack(alignment: .top, spacing: 6) {
                                    ReplyIcon(size: 24, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                                    CompletedResponseView(text: context.state.lastResponse)
                                        .foregroundStyle(.primary)
                                }
                                .layoutValue(key: ResponseContentKey.self, value: true)
                            } else {
                                // プロンプトと返答、両方あれば両方表示する（完了時も入力を残す）
                                if !context.state.lastPrompt.isEmpty {
                                    HStack(alignment: .center, spacing: 6) {
                                        PromptIcon(size: 24, color: .secondary)
                                        ActivityMarqueeText(context.state.lastPrompt)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                                if !context.state.lastResponse.isEmpty {
                                    if status == .done && context.state.lastResponse.count >= 16 {
                                        // 完了時は読める先頭を残し、はみ出した続きだけ2周流す
                                        HStack(alignment: .top, spacing: 6) {
                                            ReplyIcon(size: 24, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                                            CompletedResponseView(text: context.state.lastResponse)
                                                .foregroundStyle(.primary)
                                        }
                                        .layoutValue(key: ResponseContentKey.self, value: true)
                                    } else {
                                        // マーキーは 1 行なのでアイコンは中央揃え（.top だと浮く）
                                        HStack(alignment: .center, spacing: 6) {
                                            ReplyIcon(size: 24, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                                            ActivityMarqueeText(context.state.lastResponse)
                                                .foregroundStyle(.primary)
                                        }
                                    }
                                }
                                if context.state.lastPrompt.isEmpty, context.state.lastResponse.isEmpty,
                                   !context.state.detail.isEmpty {
                                    Text(context.state.detail)
                                        .font(.footnote)
                                        .lineLimit(2)
                                        .contentTransition(.opacity)
                                }
                                LogLinesView(logs: context.state.recentLogs, maxLines: 1)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 4)
                    .ignoresSafeArea(.container, edges: .bottom)
                }
            } compactLeading: {
                CompactStatusIcon(status: status, provider: provider, size: 20,
                                  startedAt: context.state.startedAt,
                                  animated: context.state.compactAnimated,
                                  changeTrigger: context.state.toolCount)
            } compactTrailing: {
                // 実行中のツール、または完了時は直近ツールのチェックマーク付き
                // アイコン。どちらも無いときは透明なプレースホルダを置く
                // （空にすると幅が詰まって Dynamic Island の大きさが変わるため）。
                // タップでこのセッションの詳細（回答 UI 込み）を開く
                Link(destination: URL(string: "claudelive://session/\(context.attributes.sessionId)")!) {
                    Group {
                        if status == .question {
                            Image(systemName: "questionmark")
                                .resizable()
                                .scaledToFit()
                                .foregroundStyle(status.color(for: provider))
                        } else if !context.state.currentTool.isEmpty {
                            toolRunningIcon(context.state.currentTool, provider: provider)
                                .foregroundStyle(status.color(for: provider))
                        } else if let name = toolCheckmarkSymbolName(context.state.lastTool, provider: provider) {
                            // ツール実行が終わったら（完了時に限らず作業中の合間も）
                            // 直近ツールのチェックマーク付きアイコンを出す。
                            // バッジ付きは横長なので正方形に fit させると本体が
                            // 縮んで左に寄る → 高さ基準で合わせ、幅はみ出しは許容
                            Image(name)
                                .renderingMode(.template)
                                .resizable()
                                .scaledToFit()
                                .foregroundStyle(provider.accentColor)
                                // ターミナル（Bash）だけ大きめに見せる
                                .frame(height: context.state.lastTool == "Bash" ? 20 * 1.4 * 1.5 * 1.5 : 20)
                        } else {
                            Color.clear
                        }
                    }
                    .frame(width: 20, height: 20)
                }
            } minimal: {
                // 他のライブアクティビティと同居して1つしか出せないとき。
                // ツール実行中はそのツールのアイコン、それ以外は状態アイコン
                // （完了なら Claude の完了マーク）
                if !context.state.currentTool.isEmpty {
                    toolRunningIcon(context.state.currentTool, provider: provider)
                        .frame(width: 18, height: 18)
                        .foregroundStyle(status.color(for: provider))
                } else {
                    StatusIconView(status: status, provider: provider, size: 18, animateWhenWorking: false)
                }
            }
            .keylineTint(status.color(for: provider))
        }
        // watchOS 11+ の Smart Stack にも表示する（WWDC24 "Bring your Live
        // Activity to Apple Watch"）。対応ファミリーは .small のみ。
        // 新規の watch ターゲットは不要 — 既存の LockScreenView が
        // activityFamily 環境値で分岐して描画する
        .supplementalActivityFamilies([.small])
    }
}

/// Claude のマーク。[[claude-usage-bar-app]] と同じ ClaudeSpark.png を使う。
/// 元画像に Claude カラーが付いているので tint はかけずそのまま表示し、
/// 読み込みに失敗した場合だけ SF Symbols にフォールバックする
struct ClaudeMarkIcon: View {
    let size: CGFloat
    var color: Color = .primary

    var body: some View {
        if let image = FrameAnimation.bundledImage("ClaudeSpark") {
            image
                .resizable()
                .scaledToFit()
                .frame(width: size, height: size)
        } else {
            Image(systemName: "sparkle")
                .font(.system(size: size))
                .foregroundStyle(color)
                .frame(width: size, height: size)
        }
    }
}

/// SF Symbols を実寸指定で描く小アイコン。
/// `.font()` 指定だとシンボルごとに見た目の大きさがまちまちになるため、
/// ClaudeMarkIcon（PNG）と縦横のサイズ基準を揃える目的で使う
struct SmallSymbolIcon: View {
    let name: String
    let size: CGFloat
    var color: Color = .secondary

    var body: some View {
        Image(systemName: name)
            .resizable()
            .scaledToFit()
            .frame(width: size, height: size)
            .foregroundStyle(color)
    }
}

/// プロンプト（ユーザー入力）行のアイコン。カスタム SF Symbol
/// （person.bubble.right.fill のカスタム版）を使う
struct PromptIcon: View {
    let size: CGFloat
    var color: Color = .secondary

    var body: some View {
        Image("ClaudePersonBubble")
            .renderingMode(.template)
            .resizable()
            .scaledToFit()
            .frame(width: size, height: size)
            .foregroundStyle(color)
    }
}

/// Claude の返答行のアイコン。カスタム SF Symbol
/// （bubble.left.fill のカスタム版）を使う
struct ReplyIcon: View {
    let size: CGFloat
    var color: Color = .primary
    var status: ClaudeStatus? = nil
    /// この値が変わるたびに一度だけ揺れる（新しい返答が来たときのフィードバック用）
    var changeTrigger: String = ""
    var provider: SessionProvider = .claude

    private var symbolName: String {
        status == .done ? "\(provider.symbolPrefix)BubbleReplyDone" : "\(provider.symbolPrefix)BubbleReply"
    }

    var body: some View {
        Image(symbolName)
            .renderingMode(.template)
            .resizable()
            .scaledToFit()
            .frame(width: size, height: size)
            .foregroundStyle(color)
            .symbolEffect(.wiggle, value: changeTrigger)
    }
}

/// 状態アイコン。
/// - 作業中（.working）: Claude ブランドのモーフィングアニメ
/// - 完了（.done）/ 質問（.question）: 専用のカスタムシンボル（Claude カラー）
/// - それ以外: 通常の SF Symbols アイコン
///
/// 見た目の大きさが揃うよう、SF Symbols とカスタムシンボルはどちらも
/// 同じ実寸（size）を基準に描画する
/// Dynamic Island のコンパクト領域専用の状態アイコン。
/// フォントマスク方式のコマ送り（SpinnerProofView）はコンパクト領域では
/// マスクのタイミングが噛み合わず塗り潰し矩形が出てしまうため、ここでは
/// カスタムシンボル + symbolEffect というネイティブの手段でアニメーションさせる
struct CompactStatusIcon: View {
    let status: ClaudeStatus
    var provider: SessionProvider = .claude
    let size: CGFloat
    /// DigitFrameSpinnerView のタイマー起点（ライブアクティビティの startedAt）
    let startedAt: Date
    /// true でコマ送り版（CompactSpinnerView）を使う。過去にこれが原因で
    /// ライブアクティビティが強制終了される不具合を起こしたため、既定は false
    /// （静止版）にし、アプリの設定画面から検証用にオン/オフできるようにした
    var animated: Bool = false
    /// この値が変わるたびに一度だけバウンドする（ツール切り替わりのフィード
    /// バック用）。symbolEffect の .repeating はコンパクト領域では連続再生
    /// されない（実機で確認）ため、value トリガー方式に変更した
    var changeTrigger: Int = 0

    private var symbolName: String {
        switch status {
        case .done:     return "\(provider.symbolPrefix)BadgeCheckmark"
        case .question: return "\(provider.symbolPrefix)BadgeQuestionmark"
        default:        return ""
        }
    }

    var body: some View {
        Group {
            if provider == .codex && status == .working {
                Image("CodexMark")
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(provider.accentColor)
                    .symbolEffect(.bounce, value: changeTrigger)
            } else if status == .working && animated {
                CompactSpinnerView(size: size)
            } else if status == .working {
                Image("ClaudeMark")
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(status.color(for: provider))
                    .symbolEffect(.bounce, value: changeTrigger)
            } else if symbolName.isEmpty {
                Image(systemName: status.icon)
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(status.color(for: provider))
                    .symbolEffect(.pulse, options: .repeating, isActive: status.needsAttention)
            } else {
                Image(symbolName)
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    // 完了はブランドカラー固定、質問は状態色（インディゴ）にする
                    .foregroundStyle(status == .question ? status.color(for: provider) : provider.accentColor)
                    .symbolEffect(.pulse, options: .repeating,
                                  isActive: status == .question)
            }
        }
        .frame(width: size, height: size)
    }
}

struct StatusIconView: View {
    let status: ClaudeStatus
    var provider: SessionProvider = .claude
    let size: CGFloat
    var animateWhenWorking: Bool = true

    /// Claude マークにバッジを付けたカスタムシンボル（Assets.xcassets）
    private var customSymbolName: String? {
        switch status {
        case .done:     return "\(provider.symbolPrefix)BadgeCheckmark"
        case .question: return "\(provider.symbolPrefix)BadgeQuestionmark"
        default:        return nil
        }
    }

    var body: some View {
        Group {
            if provider == .codex && status == .working {
                Image("CodexMark")
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(provider.accentColor)
                    .symbolEffect(.pulse, options: .repeating, isActive: animateWhenWorking)
            } else if status == .working && animateWhenWorking {
                SpinnerProofView(size: size, color: status.color(for: provider))
            } else if status == .working {
                // アニメーションを使わない場所（DI minimal・watch AOD 中）は
                // 金槌マークではなく Claude マークの静止版で表す
                ClaudeMarkIcon(size: size, color: status.color(for: provider))
            } else if let name = customSymbolName {
                Image(name)
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    // 完了はブランドカラー固定、質問は状態色（インディゴ）にする
                    .foregroundStyle(status == .question ? status.color(for: provider) : provider.accentColor)
            } else {
                Image(systemName: status.icon)
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(status.color(for: provider))
                    .symbolEffect(.pulse, isActive: status.needsAttention)
                    .symbolEffect(.bounce.byLayer, options: .repeating, isActive: status == .compacting)
            }
        }
        .frame(width: size, height: size)
    }
}

private struct LockScreenView: View {
    let context: ActivityViewContext<ClaudeActivityAttributes>
    private var provider: SessionProvider { context.state.sessionProvider }

    // watchOS の Smart Stack から描画されるときだけ .small になる。
    // iOS のロック画面 / バナーでは常に nil（＝ .small 以外の扱い）
    @Environment(\.activityFamily) private var activityFamily
    @Environment(\.isActivityFullscreen) private var isActivityFullscreen

    private var status: ClaudeStatus { ClaudeStatus(context.state.status) }

    var body: some View {
        if activityFamily == .small {
            WatchSmallView(context: context, status: status)
        } else if isActivityFullscreen {
            StandByView(context: context, status: status)
                .activityBackgroundTint(.black)
        } else {
            fullBody
                .activityBackgroundTint(.clear)
        }
    }

    private var fullBody: some View {
        ReplyPriorityLayout(maxHeight: 136, spacing: status == .done ? 4 : 6) {
            if !context.state.question.isEmpty {
                // 質問中は質問文と選択肢ボタンだけを表示する
                // （ヘッダー・経過時間・状態行・会話・ツール数はすべて省く）
                QuestionView(sessionId: context.attributes.sessionId,
                             question: context.state.question,
                             options: context.state.options,
                             tint: status.color(for: provider),
                             compact: false,
                             isSettled: context.state.textSettled,
                              questionCount: context.state.questionCount)
            } else {
                // ヘッダ: 状態アイコン（作業中はアニメーション）・状態ラベル・経過時間
                HStack(spacing: 6) {
                    StatusIconView(status: status, provider: provider, size: 26)
                    Text(status.label)
                        .font(.headline)
                        .foregroundStyle(status.needsAttention ? status.color(for: provider) : .primary)
                    if !context.state.currentTool.isEmpty {
                        Text(context.state.currentTool)
                            .font(.subheadline.monospaced())
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    Spacer()
                    if !context.state.model.isEmpty {
                        Text(shortModelName(context.state.model))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    ElapsedTimerText(startedAt: context.state.workStartedAt ?? context.state.startedAt,
                                     endedAt: context.state.workEndedAt)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        // Text(timerInterval:) は「表示しうる最大幅」を先に確保するため、
                        // 放置するとモデル名との間に大きな余白ができる。実測に近い幅で固定する。
                        // 1時間以上だと "H:MM:SS" になり幅が増えるので、58pt では折り返して
                        // 2行になっていた。3桁分の余裕を見て広げる
                        .frame(width: 74, alignment: .trailing)
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                // 詳細
                if !context.state.detail.isEmpty {
                    HStack(spacing: 8) {
                        Color.clear.frame(width: 26, height: 0)
                        Text(context.state.detail)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                            .contentTransition(.opacity)
                        Spacer(minLength: 0)
                    }
                }

                // バックグラウンドタスクの進捗。ツールログや返答表示の邪魔にならない
                // 控えめな 1 行として添える
                if (context.state.taskTotal ?? 0) > 0 {
                    HStack(spacing: 8) {
                        Color.clear.frame(width: 26, height: 0)
                        TaskProgressLine(done: context.state.taskDone ?? 0,
                                          total: context.state.taskTotal ?? 0,
                                          active: context.state.taskActive ?? "")
                        Spacer(minLength: 0)
                    }
                }

                // 完了時、返答が長くて場所を取るならツールログは省いて
                // 返答を複数行で優先表示する（マーキーは1行しか流せないため）
                let expandResponse = status == .done && context.state.lastResponse.count >= 100
                if expandResponse {
                    if !context.state.lastPrompt.isEmpty {
                        HStack(alignment: .center, spacing: 6) {
                            PromptIcon(size: status == .done ? 18 : 26, color: .secondary)
                            ActivityMarqueeText(context.state.lastPrompt)
                                .foregroundStyle(.secondary)
                        }
                    }
                    HStack(alignment: .top, spacing: 6) {
                        ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                        CompletedResponseView(text: context.state.lastResponse)
                            .foregroundStyle(.primary)
                    }
                    .layoutValue(key: ResponseContentKey.self, value: true)
                } else {
                    // 直近のやり取り: ユーザー入力 → Claude の返答
                    if !context.state.lastPrompt.isEmpty {
                        // マーキーは 1 行なのでアイコンは中央揃え（.top だと浮く）
                        HStack(alignment: .center, spacing: 6) {
                            PromptIcon(size: status == .done ? 18 : 26, color: .secondary)
                            ActivityMarqueeText(context.state.lastPrompt)
                                .foregroundStyle(.secondary)
                        }
                    }
                    if !context.state.lastResponse.isEmpty {
                        if status == .done && context.state.lastResponse.count >= 16 {
                            // 完了時は読める先頭を残し、はみ出した続きだけ2周流す
                            HStack(alignment: .top, spacing: 6) {
                                ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                                CompletedResponseView(text: context.state.lastResponse)
                                    .foregroundStyle(.primary)
                            }
                            .layoutValue(key: ResponseContentKey.self, value: true)
                        } else {
                            HStack(alignment: .center, spacing: 6) {
                                ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: context.state.lastResponse, provider: provider)
                                ActivityMarqueeText(context.state.lastResponse)
                                    .foregroundStyle(.primary)
                            }
                        }
                    }

                    LogLinesView(logs: context.state.recentLogs, maxLines: 2)

                }
            }
            if context.state.question.isEmpty {
                SessionUsageView(tokenCount: context.state.tokenCount,
                                 weeklyUsedPercent: context.state.weeklyUsedPercent)
            }
        }
        .padding(12)
        .opacity(context.isStale ? 0.5 : 1.0)
        .overlay(alignment: .topTrailing) {
            if context.isStale {
                Label("接続が途切れています", systemImage: "wifi.slash")
                    .font(.caption2)
                    .foregroundStyle(.orange)
                    .padding(8)
            }
        }
    }
}

/// StandBy can receive a shorter canvas than the landscape screen itself.
/// Reserve a bottom inset even when the host doesn't report the home indicator.
struct StandBySizing {
    let insets: EdgeInsets
    let contentSize: CGSize
    let compact: Bool
    let statusSize: CGFloat
    let nameSize: CGFloat
    let bodySize: CGFloat
    let footerSize: CGFloat
    let spacing: CGFloat

    init(size: CGSize, safeArea: EdgeInsets = EdgeInsets()) {
        let width = size.width.isFinite ? max(1, size.width) : 600
        let height = size.height.isFinite ? max(1, size.height) : 280
        compact = height < 280
        let tight = height < 220
        let horizontal: CGFloat = compact ? 16 : 24
        let top: CGFloat = tight ? 8 : 16
        let bottom: CGFloat = tight ? 12 : 20
        insets = EdgeInsets(top: max(top, safeArea.top),
                            leading: max(horizontal, safeArea.leading),
                            bottom: max(bottom, safeArea.bottom + 8),
                            trailing: max(horizontal, safeArea.trailing))
        contentSize = CGSize(width: max(1, width - insets.leading - insets.trailing),
                             height: max(1, height - insets.top - insets.bottom))
        statusSize = tight ? 26 : compact ? 32 : 40
        nameSize = tight ? 18 : compact ? 22 : 28
        bodySize = tight ? 14 : compact ? 16 : 18
        footerSize = tight ? 12 : compact ? 14 : 16
        spacing = tight ? 6 : compact ? 8 : 12
    }
}

/// 状態とセッション名は同じ行に置き、本文だけを空き高さに合わせる。
private struct StandByView: View {
    let context: ActivityViewContext<ClaudeActivityAttributes>
    private var provider: SessionProvider { context.state.sessionProvider }
    let status: ClaudeStatus
    @Environment(\.isLuminanceReduced) private var isLuminanceReduced

    private var sessionTitle: String {
        if !context.state.sessionName.isEmpty { return context.state.sessionName }
        if !context.state.sessionTitle.isEmpty { return context.state.sessionTitle }
        return context.attributes.projectName
    }

    private var hasQuestion: Bool { !context.state.question.isEmpty }

    var body: some View {
        // ActivityKit first asks for the view's ideal height. A root
        // GeometryReader answers 10 pt, collapsing the StandBy canvas before
        // its children are measured. Offer intrinsically sized layouts instead.
        ViewThatFits(in: .vertical) {
            canvas(height: 280)
            canvas(height: 240)
            canvas(height: 200)
            canvas(height: 160)
        }
    }

    private func canvas(height: CGFloat) -> some View {
        let sizing = StandBySizing(size: CGSize(width: 600, height: height))
        return content(sizing)
            .padding(sizing.insets)
            .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private func content(_ sizing: StandBySizing) -> some View {
        ReplyPriorityLayout(maxHeight: sizing.contentSize.height, spacing: sizing.spacing) {
            HStack(spacing: sizing.spacing) {
                let iconSize = hasQuestion ? min(26, sizing.statusSize) : sizing.statusSize
                StatusIconView(status: status, provider: provider, size: iconSize,
                               animateWhenWorking: !isLuminanceReduced)
                Text(context.isStale ? "接続待ち" : status.label)
                    .font(.system(size: iconSize, weight: .bold))
                    .foregroundStyle(context.isStale ? .orange : status.color(for: provider))
                    .lineLimit(1).fixedSize(horizontal: true, vertical: false)
                MarqueeText(sessionTitle, font: SessionTitleFont.uiFont(ofSize: sizing.nameSize),
                            isEnabled: !isLuminanceReduced)
                    .foregroundStyle(.primary)
                if hasQuestion, sizing.contentSize.height < 200 {
                    Button(intent: OpenSessionIntent(sessionId: context.attributes.sessionId)) {
                        Image(systemName: "square.and.pencil")
                            .font(.system(size: sizing.nameSize))
                            .frame(width: 32, height: 32)
                    }
                    .buttonStyle(.plain).foregroundStyle(provider.accentColor)
                    .accessibilityLabel("他の答えを入力")
                    .disabled(context.isStale)
                }
            }

            if hasQuestion {
                StandByQuestionView(context: context, tint: status.color(for: provider),
                                    compact: sizing.compact,
                                    showsCustomAnswer: sizing.contentSize.height >= 200)
                    .disabled(context.isStale)
            } else if !context.state.lastPrompt.isEmpty || !context.state.lastResponse.isEmpty {
                ReplyPriorityLayout(spacing: sizing.compact ? 4 : 8) {
                    if !context.state.lastPrompt.isEmpty {
                        HStack(spacing: 8) {
                            PromptIcon(size: sizing.bodySize, color: .secondary)
                            MarqueeText(context.state.lastPrompt, font: .systemFont(ofSize: sizing.bodySize),
                                        isEnabled: !isLuminanceReduced)
                                .foregroundStyle(.secondary)
                        }
                    }
                    if !context.state.lastResponse.isEmpty {
                        HStack(alignment: .top, spacing: 8) {
                            ReplyIcon(size: sizing.bodySize, color: provider.accentColor, status: status,
                                      changeTrigger: context.state.lastResponse, provider: provider)
                            CompletedResponseView(text: context.state.lastResponse,
                                                  basePointSize: sizing.bodySize,
                                                  isAnimationEnabled: !isLuminanceReduced)
                                .foregroundStyle(.primary)
                        }
                        .layoutValue(key: ResponseContentKey.self, value: true)
                    }
                }
                .layoutValue(key: ResponseContentKey.self, value: true)
            } else if !context.state.detail.isEmpty {
                Text(context.state.detail)
                    .font(.system(size: sizing.bodySize))
                    .foregroundStyle(.secondary).lineLimit(1)
            }

            if !hasQuestion {
                HStack(spacing: 12) {
                    Text(context.state.currentTool.isEmpty
                         ? context.attributes.projectName : context.state.currentTool)
                        .lineLimit(1).minimumScaleFactor(0.75)
                    Spacer(minLength: 8)
                    ElapsedTimerText(startedAt: context.state.workStartedAt ?? context.state.startedAt,
                                     endedAt: context.state.workEndedAt)
                        .monospacedDigit().fixedSize()
                }
                .font(.system(size: sizing.footerSize)).foregroundStyle(.secondary)
                SessionUsageView(tokenCount: context.state.tokenCount,
                                 weeklyUsedPercent: context.state.weeklyUsedPercent,
                                 font: .system(size: sizing.footerSize))
            }
        }
    }
}

private struct StandByQuestionView: View {
    let context: ActivityViewContext<ClaudeActivityAttributes>
    let tint: Color
    var compact = false
    var showsCustomAnswer = true

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 6 : 10) {
            MarqueeText(context.state.question,
                        font: .systemFont(ofSize: compact ? 18 : 22, weight: .semibold))

            if (context.state.questionCount ?? 1) > 1 {
                Button(intent: OpenSessionIntent(sessionId: context.attributes.sessionId)) {
                    Label("\(context.state.questionCount ?? 0)件の質問 · アプリで回答",
                          systemImage: "list.bullet.rectangle")
                        .font(.headline)
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.plain)
                .foregroundStyle(tint)
            } else {
                let options = Array(context.state.options.prefix(4))
                ForEach(0..<((options.count + 1) / 2), id: \.self) { row in
                    HStack(spacing: compact ? 6 : 10) {
                        ForEach(0..<2, id: \.self) { column in
                            let index = row * 2 + column
                            if index < options.count {
                                Button(intent: AnswerQuestionIntent(
                                    sessionId: context.attributes.sessionId, answer: options[index])) {
                                    Text(options[index])
                                        .font(.system(size: compact ? 16 : 18, weight: .bold))
                                        .lineLimit(2)
                                        .minimumScaleFactor(0.75)
                                        .multilineTextAlignment(.center)
                                        .frame(maxWidth: .infinity, minHeight: compact ? 38 : 44)
                                        .padding(.horizontal, 10)
                                        .padding(.vertical, compact ? 3 : 6)
                                        .foregroundStyle(.white)
                                        .background(tint, in: RoundedRectangle(cornerRadius: 14))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                if showsCustomAnswer {
                    Button(intent: OpenSessionIntent(sessionId: context.attributes.sessionId)) {
                        Label("他の答えを入力…", systemImage: "square.and.pencil")
                            .font(.subheadline)
                            .frame(maxWidth: .infinity, minHeight: 32, alignment: .leading)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(tint)
                }
            }
        }
    }
}

/// watchOS の Smart Stack（.small ファミリーのみ対応）向けの表示。
/// スペースが極小なのでテキスト中心・要素は最小限にする。
/// 質問中もボタンは出さず文字で知らせるだけ（回答は iPhone 側で行う）
private struct WatchSmallView: View {
    let context: ActivityViewContext<ClaudeActivityAttributes>
    private var provider: SessionProvider { context.state.sessionProvider }
    let status: ClaudeStatus

    // 常時表示（Always On Display）中は輝度を落として表示される。
    // 色をそのまま使うと明るすぎるので、暗めの表現に切り替える
    @Environment(\.isLuminanceReduced) private var isLuminanceReduced

    private var tint: Color { isLuminanceReduced ? .white.opacity(0.6) : status.color(for: provider) }

    /// インライン Markdown（**強調**・`コード` など）を解釈する
    private func styled(_ text: String) -> AttributedString {
        (try? AttributedString(
            markdown: text,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)))
            ?? AttributedString(text)
    }

    var body: some View {
        // Link・.widgetURL・openAppWhenRun 付き AppIntent をすべて試したが、
        // いずれも実機で期待通り動かなかった（前者2つは無反応、Intent 版は
        // ウィジェット拡張機能が属する iOS 側のアプリを開いてしまい、
        // Watch アプリを開けなかった）。誤動作より無反応の方がましなので、
        // タップを乗っ取らない素のコンテンツに戻す
        content
    }

    private var content: some View {
        ReplyPriorityLayout(maxHeight: 100, spacing: 3) {
            HStack(alignment: .top, spacing: 5) {
                // 常時表示(AOD)中はアニメを止めて静止アイコンに（輝度を落とす必要があり、
                // このアイコン画像は固定色のため tint を効かせられないため）
                StatusIconView(status: status, provider: provider, size: 22, animateWhenWorking: !isLuminanceReduced)
                ActivityMarqueeText(context.state.sessionName.isEmpty
                                    ? context.attributes.projectName
                                    : context.state.sessionName,
                                    compact: true, weight: .bold, sessionTitle: true,
                                    isEnabled: !isLuminanceReduced)
                // 状態ラベル（「作業中」など）はセッション名の隣に置く
                Text(status.label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .layoutPriority(-1)
                Spacer(minLength: 0)
                // 実行中ツール、または直近ツールのチェックマーク付きアイコン。
                // DI コンパクトの右端と同じ考え方で 1 行目の右端に置く
                Group {
                    if !context.state.currentTool.isEmpty {
                        toolRunningIcon(context.state.currentTool, provider: provider)
                            // 常時表示(AOD)中も色を変えない（他のアイコンは輝度を落とすが、
                            // これは要望によりそのままにする）
                            .foregroundStyle(status.color(for: provider))
                    } else if let name = toolCheckmarkSymbolName(context.state.lastTool, provider: provider) {
                        Image(name)
                            .renderingMode(.template)
                            .resizable()
                            .scaledToFit()
                            .foregroundStyle(status.color(for: provider))
                            // ターミナル（Bash）だけ大きめに見せるが、行の高さ（22pt）を
                            // 超えると Smart Stack のカードからはみ出すので上限を設ける
                            .frame(height: context.state.lastTool == "Bash" ? 22 : 16)
                    } else {
                        Color.clear
                    }
                }
                // 行の先頭アイコン（22pt）と同じ高さの枠に収め、上端で揃える
                .frame(width: 16, height: 22, alignment: .top)
                .clipped()
            }

            if !context.state.question.isEmpty {
                let count = context.state.questionCount ?? 1
                // 質問の見出しとマーキーを出し、長い質問もカード内で読めるようにする。
                HStack(spacing: 4) {
                    Image(systemName: "questionmark.circle.fill")
                        .foregroundStyle(provider.accentColor)
                    Text(count > 1 ? "質問 \(count)件" : "質問")
                        .font(.caption2.bold())
                }
                ActivityMarqueeText(context.state.question, compact: true,
                                    isEnabled: !isLuminanceReduced)
                // Smart Stack では単一質問でも選択肢を出さない。
                // カードのタップで Watch アプリが開き、そこで回答する
                // （選択肢の全文や自由入力はアプリでしか扱えないため、
                // 狭いカードに切り詰めたボタンを並べるより一貫していて誤答も防げる）
                Text("アプリで回答してください")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            } else {
                if !context.state.currentTool.isEmpty {
                    Text(context.state.currentTool)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                // 状態の一言だけでなく、Claude が実際に何を言った/何を頼まれたかを
                // 一番情報量の多い内容として表示する（返答 > 入力 > detail の優先順）
                if !context.state.lastResponse.isEmpty {
                    // 読める行はカードに残し、収まらない続きだけ2周流す。
                    // AOD と Reduce Motion では静止し、表のセルもテキストで残す。
                    if status == .done {
                        CompletedResponseView(text: context.state.lastResponse, basePointSize: 11,
                                              isAnimationEnabled: !isLuminanceReduced)
                            .layoutValue(key: ResponseContentKey.self, value: true)
                    } else {
                        ActivityMarqueeText(CompletedResponseView.displayText(context.state.lastResponse),
                                            compact: true, isEnabled: !isLuminanceReduced)
                    }
                } else if !context.state.lastPrompt.isEmpty {
                    ActivityMarqueeText(String(styled(context.state.lastPrompt).characters),
                                        compact: true, isEnabled: !isLuminanceReduced)
                        .foregroundStyle(.secondary)
                } else if !context.state.detail.isEmpty {
                    Text(context.state.detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
    }
}

/// Claude からの質問と選択肢ボタン。
/// タップすると AnswerQuestionIntent（アプリ本体プロセスで実行）が
/// Mac デーモンの /answer に回答を POST し、保留中の PreToolUse フックが
/// decision JSON で解決されて Claude が続行する
struct QuestionView: View {
    let sessionId: String
    let question: String
    let options: [String]
    let tint: Color
    let compact: Bool
    var isSettled: Bool = false
    /// AskUserQuestion に含まれる質問の総数（nil / 1 は単一質問）
    var questionCount: Int? = nil

    /// 2 問以上あるか。ライブアクティビティは 1 問目しか描けないので、
    /// このときは選択肢を出さずアプリへ誘導する
    private var isMultiQuestion: Bool { (questionCount ?? 1) > 1 }

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 5 : 8) {
            // 回答待ちの間、一定速度で全文を繰り返し表示する。
            ActivityMarqueeText(question, compact: compact,
                                weight: compact ? .regular : .semibold)
                .foregroundStyle(.primary)

            let items = isMultiQuestion ? [] : Array(options.prefix(4))
            if isMultiQuestion {
                // 選択肢を出すと 1 問目だけ答えて残りが未回答のまま
                // Claude に返ってしまうため、アプリで答えてもらう
                Link(destination: URL(string: "claudelive://session/\(sessionId)")!) {
                    HStack(spacing: 5) {
                        Image(systemName: "list.bullet.rectangle")
                        Text("\(questionCount ?? 0)件の質問 — アプリで回答")
                            .font(compact ? .caption2.weight(.semibold) : .footnote.weight(.semibold))
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, compact ? 5 : 7)
                    .background(tint.opacity(0.25), in: RoundedRectangle(cornerRadius: 8))
                }
                .padding(.horizontal, 6)
                .padding(.bottom, 4)
            } else if compact && items.count <= 3 {
                // Dynamic Island・選択肢 3 個以下: 1 行に横並び。
                // 3 個までは横幅に余裕があり折り返さない（4 個だけが問題になる）
                HStack(spacing: 5) {
                    ForEach(Array(items.enumerated()), id: \.offset) { _, label in
                        answerButton(label)
                    }
                }
                .padding(.horizontal, 6)
                .padding(.bottom, 4)
            } else {
                // ロック画面、および DI で選択肢 4 個: 2 列グリッド。
                // 1 行 4 個だと横幅が狭すぎて長い単語が折り返し、DI の高さ上限を
                // 超えて下端が切れる事故があったため、2 列にして横幅を確保する
                let grid = ForEach(0..<((items.count + 1) / 2), id: \.self) { row in
                    HStack(spacing: 6) {
                        ForEach(0..<2, id: \.self) { column in
                            let index = row * 2 + column
                            if index < items.count {
                                answerButton(items[index])
                            }
                        }
                    }
                }
                if compact {
                    grid.padding(.horizontal, 6).padding(.bottom, 4)
                } else {
                    grid
                }
            }

            // 選択肢にない答えはアプリを開いて自由入力する（システムアラート）
            Button(intent: OpenSessionIntent(sessionId: sessionId)) {
                Text("他の答えを入力…")
                    .font(compact ? .caption2 : .caption)
                    .foregroundStyle(tint)
            }
            .buttonStyle(.plain)
            .padding(.horizontal, compact ? 6 : 0)
            .padding(.bottom, compact ? 4 : 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func answerButton(_ label: String) -> some View {
        Button(intent: AnswerQuestionIntent(sessionId: sessionId, answer: label)) {
            Text(label)
                .font(compact ? .caption2.bold() : .subheadline.bold())
                // 1 行に収まらない選択肢ラベルは、縮小だけでなく折り返しでも読めるようにする
                // （選択肢の文言が読めないまま押させるのを避ける）
                .lineLimit(2)
                .minimumScaleFactor(0.55)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white)
                // 1 行のラベルと 2 行のラベルが同じ行内に並んでも高さが揃うよう、
                // 常に 2 行ぶんの高さを確保する（短いラベルは上下中央に収まる）
                .frame(maxWidth: .infinity, minHeight: compact ? 24 : 32)
                .padding(.vertical, compact ? 6 : 10)
                .padding(.horizontal, compact ? 8 : 6)
                .background(tint, in: Capsule())
        }
        .buttonStyle(.plain)
    }
}

/// バックグラウンドタスク（タスクリスト）の進捗を示す控えめな 1 行。
/// checklist アイコン + "done/total" + 進行中タスクの activeForm
struct TaskProgressLine: View {
    let done: Int
    let total: Int
    let active: String

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: "checklist")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text("\(done)/\(total)")
                .font(.caption2)
                .foregroundStyle(.secondary)
            if !active.isEmpty {
                Text(active)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }
}

/// 直近ツールログの共通表示
struct LogLinesView: View {
    let logs: [String]
    let maxLines: Int

    /// デーモンは "SFSymbol名|本文" 形式で送ってくる（絵文字は使わない）。
    /// 区切りが無い古い形式は本文のみとして扱い、汎用アイコンを添える
    private func split(_ line: String) -> (symbol: String, text: String) {
        guard let index = line.firstIndex(of: "|") else {
            return ("wrench.and.screwdriver", line)
        }
        return (String(line[line.startIndex..<index]),
                String(line[line.index(after: index)...]))
    }

    var body: some View {
        if !logs.isEmpty {
            VStack(alignment: .leading, spacing: 1) {
                ForEach(Array(logs.prefix(maxLines).enumerated()), id: \.offset) { index, line in
                    let parsed = split(line)
                    HStack(alignment: .center, spacing: 5) {
                        SmallSymbolIcon(name: parsed.symbol, size: 10,
                                        color: index == 0 ? .secondary : .secondary.opacity(0.6))
                        Text(parsed.text)
                            .font(.caption2.monospaced())
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                    .foregroundStyle(index == 0 ? .secondary : .tertiary)
                }
            }
        }
    }
}

/// 経過時間タイマー（システム側で毎秒更新されるのでプッシュ不要）
struct ElapsedTimerText: View {
    let startedAt: Date
    var endedAt: Date? = nil

    var body: some View {
        Group {
            if let endedAt {
                Text(workDurationText(from: startedAt, to: endedAt))
            } else {
                Text(startedAt, style: .timer)
            }
        }
        .multilineTextAlignment(.trailing)
    }
}

/// 完了後の所要時間。24時間を超えた作業も日付で折り返さない。
func workDurationText(from start: Date, to end: Date) -> String {
    let seconds = max(0, Int(end.timeIntervalSince(start)))
    if seconds >= 3600 {
        return String(format: "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
    }
    return String(format: "%d:%02d", seconds / 60, seconds % 60)
}
