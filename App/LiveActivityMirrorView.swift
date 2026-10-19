import SwiftUI

/// ライブアクティビティ（ロック画面）の見た目をアプリ内でそのまま再現する
/// プレビュー。Widget/ClaudeLiveActivityWidget.swift の LockScreenView.fullBody と
/// 同じコンポーネント（StatusIconView・MarqueeText・QuestionView 等）を再利用する。
/// ActivityViewContext はアプリ側からは作れないため、ContentState と
/// attributes を直接受け取る形に分けている
struct LiveActivityMirrorView: View {
    let attributes: ClaudeActivityAttributes
    let state: ClaudeActivityAttributes.ContentState

    private var provider: SessionProvider { state.sessionProvider }

    private var status: ClaudeStatus { ClaudeStatus(state.status) }

    var body: some View {
        ReplyPriorityLayout(maxHeight: 136, spacing: status == .done ? 4 : 6) {
            if !state.question.isEmpty {
                QuestionView(sessionId: attributes.sessionId,
                             question: state.question,
                             options: state.options,
                             tint: status.color(for: provider),
                             compact: false,
                             isSettled: state.textSettled,
                              questionCount: state.questionCount)
            } else {
                // ヘッダ: 状態アイコン（作業中はアニメーション）・状態ラベル・
                // 実行中ツール・モデル名・経過時間
                HStack(spacing: 6) {
                    StatusIconView(status: status, provider: provider, size: 26)
                    Text(status.label)
                        .font(.headline)
                        .foregroundStyle(status.needsAttention ? status.color(for: provider) : .primary)
                    if !state.currentTool.isEmpty {
                        Text(state.currentTool)
                            .font(.subheadline.monospaced())
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    Spacer()
                    if !state.model.isEmpty {
                        Text(shortModelName(state.model))
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    ElapsedTimerText(startedAt: state.workStartedAt ?? state.startedAt,
                                     endedAt: state.workEndedAt)
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        // Text(timerInterval:) は「表示しうる最大幅」を先に確保するため、
                        // 放置するとモデル名との間に大きな余白ができる。実測に近い幅で固定する。
                        // 1時間以上だと "H:MM:SS" になり幅が増えるので広げてある
                        .frame(width: 74, alignment: .trailing)
                }
                .frame(maxWidth: .infinity, alignment: .leading)

                if !state.detail.isEmpty {
                    HStack(spacing: 8) {
                        Color.clear.frame(width: 26, height: 0)
                        Text(state.detail)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                        Spacer(minLength: 0)
                    }
                }

                let expandResponse = status == .done && state.lastResponse.count >= 100
                if expandResponse {
                    if !state.lastPrompt.isEmpty {
                        HStack(alignment: .center, spacing: 6) {
                            PromptIcon(size: status == .done ? 18 : 26, color: .secondary)
                            ActivityMarqueeText(state.lastPrompt)
                                .foregroundStyle(.secondary)
                        }
                    }
                    HStack(alignment: .top, spacing: 6) {
                        ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: state.lastResponse, provider: provider)
                        CompletedResponseView(text: state.lastResponse)
                            .foregroundStyle(.primary)
                    }
                    .layoutValue(key: ResponseContentKey.self, value: true)
                } else {
                    if !state.lastPrompt.isEmpty {
                        HStack(alignment: .center, spacing: 6) {
                            PromptIcon(size: status == .done ? 18 : 26, color: .secondary)
                            ActivityMarqueeText(state.lastPrompt)
                                .foregroundStyle(.secondary)
                        }
                    }
                    if !state.lastResponse.isEmpty {
                        if status == .done && state.lastResponse.count >= 16 {
                            // 完了時は読める先頭を残し、はみ出した続きだけ2周流す
                            HStack(alignment: .top, spacing: 6) {
                                ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: state.lastResponse, provider: provider)
                                CompletedResponseView(text: state.lastResponse)
                                    .foregroundStyle(.primary)
                            }
                            .layoutValue(key: ResponseContentKey.self, value: true)
                        } else {
                            HStack(alignment: .center, spacing: 6) {
                                ReplyIcon(size: 26, color: provider.accentColor, status: status, changeTrigger: state.lastResponse, provider: provider)
                                ActivityMarqueeText(state.lastResponse)
                                    .foregroundStyle(.primary)
                            }
                        }
                    }

                    LogLinesView(logs: state.recentLogs, maxLines: 2)

                }
            }
            if state.question.isEmpty {
                SessionUsageView(tokenCount: state.tokenCount,
                                 weeklyUsedPercent: state.weeklyUsedPercent)
            }
        }
        .padding(12)
        .modifier(LiveActivityMirrorBackground())
    }
}

private struct LiveActivityMirrorBackground: ViewModifier {
    @ViewBuilder
    func body(content: Content) -> some View {
        if #available(iOS 26.0, *) {
            content.glassEffect(.regular.tint(Color.codexBrand.opacity(0.28)),
                                in: RoundedRectangle(cornerRadius: 20))
        } else {
            content
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20))
                .background(Color.codexBrand.opacity(0.28), in: RoundedRectangle(cornerRadius: 20))
        }
    }
}
