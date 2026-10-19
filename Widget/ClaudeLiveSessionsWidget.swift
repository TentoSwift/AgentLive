import SwiftUI
import UIKit
import WidgetKit

struct SessionWidgetEntry: TimelineEntry {
    var date: Date
    var snapshot: SessionWidgetSnapshot
    var connected: Bool
}

struct SessionsWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> SessionWidgetEntry {
        SessionWidgetEntry(date: Date(), snapshot: SessionWidgetSnapshot(sessions: [
            WidgetSession(id: "preview", title: "アプリの改善", project: "ClaudeLive",
                          status: "working", summary: "変更を確認しています", startedAt: 0)
        ], updatedAt: Date()), connected: true)
    }

    func getSnapshot(in context: Context, completion: @escaping (SessionWidgetEntry) -> Void) {
        if context.isPreview { completion(placeholder(in: context)); return }
        let snapshot = SessionWidgetStore.snapshot()
        completion(SessionWidgetEntry(date: Date(), snapshot: snapshot, connected: false))
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<SessionWidgetEntry>) -> Void) {
        Task {
            let result = await SessionWidgetStore.refresh()
            let now = Date()
            let entry = SessionWidgetEntry(date: now, snapshot: result.snapshot, connected: result.connected)
            completion(Timeline(entries: [entry], policy: .after(now.addingTimeInterval(15 * 60))))
        }
    }
}

struct ClaudeLiveSessionsWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: SessionWidgetStore.kind, provider: SessionsWidgetProvider()) { entry in
            SessionsWidgetView(entry: entry)
                .containerBackground(.black.gradient, for: .widget)
        }
        .configurationDisplayName("セッション状態")
        .description("Claude・Codexの実行状態と直近の回答を表示します。")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

@available(iOS 26.0, *)
struct ClaudeLivePushSessionsWidget: Widget {
    var body: some WidgetConfiguration {
        ClaudeLiveSessionsWidget().body.pushHandler(SessionsWidgetPushHandler.self)
    }
}

@available(iOS 26.0, *)
struct SessionsWidgetPushHandler: WidgetPushHandler {
    func pushTokenDidChange(_ pushInfo: WidgetPushInfo, widgets: [WidgetInfo]) {
        let enabled = widgets.contains { $0.kind == SessionWidgetStore.kind }
        let token = enabled ? pushInfo.token.map { String(format: "%02x", $0) }.joined() : ""
        SessionWidgetStore.setPushToken(token)
        Task { await SessionWidgetStore.registerPushToken() }
    }
}

private struct SessionsWidgetView: View {
    var entry: SessionWidgetEntry
    @Environment(\.widgetFamily) private var family
    @ScaledMetric(relativeTo: .subheadline) private var titleSize: CGFloat = 15
    @ScaledMetric(relativeTo: .caption) private var summarySize: CGFloat = 12

    private var count: Int {
        switch family {
        case .systemSmall: return 1
        case .systemMedium: return 2
        default: return 3
        }
    }
    private var sessions: [WidgetSession] { Array(entry.snapshot.sessions.prefix(count)) }
    private var firstURL: URL {
        sessionURL(sessions.first?.id)
    }

    var body: some View {
        ReplyPriorityLayout(spacing: family == .systemLarge ? 8 : 6) {
            if sessions.isEmpty {
                emptyState
            } else {
                switch family {
                case .systemSmall:
                    sessionLink(sessions[0]) {
                        focusCard(sessions[0], compact: false)
                    }
                    .layoutValue(key: ResponseContentKey.self, value: true)
                case .systemMedium:
                    if sessions.count == 1 {
                        sessionLink(sessions[0]) { wideCard(sessions[0]) }
                            .layoutValue(key: ResponseContentKey.self, value: true)
                    } else {
                        HStack(alignment: .top, spacing: 12) {
                            sessionLink(sessions[0]) { focusCard(sessions[0], compact: true) }
                            Divider().overlay(Color.white.opacity(0.12))
                            sessionLink(sessions[1]) { focusCard(sessions[1], compact: true) }
                        }
                        .layoutValue(key: ResponseContentKey.self, value: true)
                    }
                default:
                    sessionLink(sessions[0]) { featuredCard(sessions[0]) }
                        .layoutValue(key: ResponseContentKey.self, value: true)
                    ForEach(Array(sessions.dropFirst())) { session in
                        Divider().overlay(Color.white.opacity(0.12))
                        sessionLink(session) { compactRow(session) }
                    }
                }
            }
            connectionFooter
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .widgetURL(firstURL)
    }

    // Small: one readable session. Medium: two independent columns.
    private func focusCard(_ session: WidgetSession, compact: Bool) -> some View {
        ReplyPriorityLayout(spacing: compact ? 4 : 6) {
            statusHeader(session, size: compact ? 16 : 24, prominent: !compact)
            title(session, size: compact ? titleSize - 2 : titleSize)
            response(session, pointSize: compact ? 12 : 13)
                .layoutValue(key: ResponseContentKey.self, value: true)
            usage(session)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // A single medium session uses the whole width instead of an empty column.
    private func wideCard(_ session: WidgetSession) -> some View {
        ReplyPriorityLayout(spacing: 6) {
            HStack(spacing: 6) {
                statusIcon(session, size: 18)
                title(session, size: titleSize)
                Text(statusLabel(session)).font(.caption.weight(.semibold))
                    .foregroundStyle(statusColor(session)).fixedSize()
            }
            response(session, pointSize: 13)
                .layoutValue(key: ResponseContentKey.self, value: true)
            usage(session)
        }
    }

    // Large: prioritise the most relevant session, then two compact summaries.
    private func featuredCard(_ session: WidgetSession) -> some View {
        ReplyPriorityLayout(spacing: 6) {
            statusHeader(session, size: 22, prominent: true)
            title(session, size: titleSize + 1)
            response(session, pointSize: 13)
                .layoutValue(key: ResponseContentKey.self, value: true)
            usage(session)
        }
    }

    private func compactRow(_ session: WidgetSession) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                statusIcon(session, size: 14)
                title(session, size: titleSize - 2)
                Text(statusLabel(session)).font(.caption2)
                    .foregroundStyle(statusColor(session)).fixedSize()
            }
            if !session.summary.isEmpty {
                MarqueeText(CompletedResponseView.displayText(session.summary),
                            font: .systemFont(ofSize: summarySize),
                            repeatCount: session.status == "done" ? 2 : nil)
                    .foregroundStyle(.secondary).privacySensitive()
            }
            usage(session)
        }
    }

    private func statusHeader(_ session: WidgetSession, size: CGFloat, prominent: Bool) -> some View {
        HStack(spacing: 6) {
            statusIcon(session, size: size)
            Text(statusLabel(session))
                .font(prominent ? .headline : .caption.weight(.semibold))
                .foregroundStyle(statusColor(session)).lineLimit(1)
            Spacer(minLength: 2)
            Text(session.provider == "codex" ? "Codex" : "Claude")
                .font(.caption2).foregroundStyle(.secondary).fixedSize()
        }
    }

    @ViewBuilder
    private func statusIcon(_ session: WidgetSession, size: CGFloat) -> some View {
        if session.status == "idle" {
            Image(systemName: "moon.zzz").font(.system(size: size))
                .foregroundStyle(.secondary).frame(width: size, height: size)
        } else {
            StatusIconView(status: ClaudeStatus(session.status), provider: SessionProvider(session.provider),
                           size: size, animateWhenWorking: false)
        }
    }

    private func title(_ session: WidgetSession, size: CGFloat) -> some View {
        MarqueeText(session.title, font: SessionTitleFont.uiFont(ofSize: size))
            .foregroundStyle(.primary).privacySensitive()
    }

    @ViewBuilder
    private func response(_ session: WidgetSession, pointSize: CGFloat) -> some View {
        if !session.summary.isEmpty {
            CompletedResponseView(text: session.summary, basePointSize: pointSize)
                .foregroundStyle(.primary).privacySensitive()
        }
    }

    private func usage(_ session: WidgetSession) -> some View {
        SessionUsageView(tokenCount: session.tokenCount, weeklyUsedPercent: session.weeklyUsedPercent)
    }

    private func statusLabel(_ session: WidgetSession) -> String {
        session.status == "idle" ? "待機" : ClaudeStatus(session.status).label
    }

    private func statusColor(_ session: WidgetSession) -> Color {
        session.status == "idle" ? .secondary
            : ClaudeStatus(session.status).color(for: SessionProvider(session.provider))
    }

    private func sessionURL(_ id: String?) -> URL {
        URL(string: id.map { "claudelive://session/\($0)" } ?? "claudelive://")!
    }

    private func sessionLink<Content: View>(_ session: WidgetSession,
                                           @ViewBuilder content: () -> Content) -> some View {
        Link(destination: sessionURL(session.id), label: content).buttonStyle(.plain)
            .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: entry.connected ? "moon.zzz" : "wifi.slash")
                .font(family == .systemSmall ? .title2 : .title).foregroundStyle(.secondary)
            Text(entry.snapshot.updatedAt == nil ? "アプリを開いてMacと接続" : "セッションなし")
                .font(.headline)
            Text(entry.connected ? "MacでClaude・Codexを起動してください" : "Macの接続を確認してください")
                .font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var connectionFooter: some View {
        if !entry.connected || entry.snapshot.sessions.count > count {
            HStack(spacing: 4) {
                if !entry.connected {
                    Image(systemName: "wifi.slash")
                    Text("保存済み")
                    if let updatedAt = entry.snapshot.updatedAt {
                        Text(updatedAt, style: .time).monospacedDigit()
                    }
                }
                Spacer(minLength: 0)
                if entry.snapshot.sessions.count > count {
                    Text("他\(entry.snapshot.sessions.count - count)件")
                }
            }
            .font(.caption2).foregroundStyle(.secondary)
        }
    }
}
