import SwiftUI

/// Claude のブランドカラー。
///
/// iOS アプリ・ウィジェット・Watch アプリの 3 ターゲットすべてで使うため、
/// 独立したファイルにしている。元は ClaudeActivityAttributes.swift にあったが、
/// あのファイルは Watch ターゲットに含まれていないため Watch から参照できなかった。
///
/// アプリ全体のアクセント（ボタン・トグル・リンクなど）は
/// 各アプリのルートで `.tint(Color.claudeBrand)` として適用している。
extension Color {
    /// Claude のブランドカラー（クレイ系オレンジ）
    static let claudeBrand = Color(red: 0.85, green: 0.47, blue: 0.34)
    /// Codex sessions use a blue-violet accent (#7C83FF).
    static let codexBrand = Color(red: 124 / 255.0, green: 131 / 255.0, blue: 1)
}

enum SessionProvider: String, Codable {
    case claude
    case codex

    init(_ value: String?) {
        self = value == "codex" ? .codex : .claude
    }

    var accentColor: Color { self == .codex ? .codexBrand : .claudeBrand }
    var symbolPrefix: String { self == .codex ? "Codex" : "Claude" }
}
