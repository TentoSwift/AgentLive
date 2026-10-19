#!/usr/bin/env python3
"""Exercise provider decoding compatibility and visible model labels from Swift sources."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
attributes = (root / 'Shared/ClaudeActivityAttributes.swift').read_text()
state = attributes[attributes.index('    struct ContentState:'):attributes.index('\n    var sessionId:')]
store = (root / 'Shared/SessionWidgetStore.swift').read_text()
widget = store[store.index('struct WidgetSession:'):store.index('\nstruct SessionWidgetSnapshot:')]
clock = (root / 'Widget/ClaudeLiveActivityWidget.swift').read_text().split('func workDurationText(', 1)[1]
clock = 'func workDurationText(' + clock
harness = r'''
let legacy = Data(#"{"status":"working","detail":"","currentTool":"","recentLogs":[],"startedAt":0,"toolCount":1,"lastPrompt":"入力","lastResponse":"返答","sessionName":"test","sessionTitle":"test","question":"","options":[],"textSettled":false,"model":"gpt-6.1-sol","compactAnimated":false,"lastTool":""}"#.utf8)
var state = try! JSONDecoder().decode(ContentState.self, from: legacy)
assert(state.provider == nil && state.sessionProvider == .codex)
assert(state.workStartedAt == nil && state.workEndedAt == nil)
let workStart = Date(timeIntervalSinceReferenceDate: 100)
assert(workDurationText(from: workStart, to: workStart.addingTimeInterval(65)) == "1:05")
assert(workDurationText(from: workStart, to: workStart.addingTimeInterval(3661)) == "1:01:01")
assert(workDurationText(from: workStart, to: workStart.addingTimeInterval(25 * 3600)) == "25:00:00")
assert(workDurationText(from: workStart, to: workStart.addingTimeInterval(-2)) == "0:00")
assert(state.tokenCount == nil && state.weeklyUsedPercent == nil)
assert(sessionUsageText(tokenCount: nil, weeklyUsedPercent: nil) == nil)
assert(sessionUsageText(tokenCount: 12345, weeklyUsedPercent: 43) == "今回 12.3k tokens ・ 週間 43%")
assert(sessionUsageText(tokenCount: 0, weeklyUsedPercent: nil) == "今回 0 tokens")
assert(sessionUsageText(tokenCount: nil, weeklyUsedPercent: 0.4) == "週間 0.4%")
assert(sessionUsageText(tokenCount: nil, weeklyUsedPercent: 0) == "週間 0%")
assert(sessionUsageText(tokenCount: -1, weeklyUsedPercent: .nan) == nil)
state.tokenCount = 12345
state.weeklyUsedPercent = 43
state.workStartedAt = workStart
state.workEndedAt = workStart.addingTimeInterval(65)
state.model = "claude-sonnet-5"
assert(state.sessionProvider == .claude)
state.provider = "codex"
let restored = try! JSONDecoder().decode(ContentState.self, from: JSONEncoder().encode(state))
assert(restored.sessionProvider == .codex && restored == state)
assert(SessionProvider("unknown") == .claude)
assert(SessionProvider.codex.symbolPrefix == "Codex" && SessionProvider.claude.symbolPrefix == "Claude")
assert(ClaudeStatus.working.color(for: .codex) == Color.codexBrand)
assert(ClaudeStatus.done.color(for: .claude) == Color.claudeBrand)
assert(ClaudeStatus.error.color(for: .codex) == ClaudeStatus.error.color(for: .claude))
assert(ClaudeStatus.question.color(for: .codex) == Color.codexBrand)
let oldWidget = Data(#"{"id":"old","title":"legacy","project":"test","status":"working","summary":"","startedAt":0}"#.utf8)
assert(try! JSONDecoder().decode(WidgetSession.self, from: oldWidget).provider == nil)
let sessions = WidgetSession.parse([["sessionId": "test", "provider": "codex", "status": "working"]])
assert(sessions.count == 1 && sessions[0].provider == "codex")
for (raw, visible) in [
    ("gpt-6.1-sol", "GPT-6.1 Sol"), ("gpt-6-astra", "GPT-6 Astra"),
    ("gpt-6-luna", "GPT-6 Luna"), ("gpt-5.6-terra", "GPT-5.6 Terra"),
    ("gpt-5.4-mini", "GPT-5.4 mini"), ("gpt-5.3-codex", "GPT-5.3 Codex"),
    ("claude-sonnet-5", "Sonnet 5"), ("claude-custom", "custom"),
    ("unrecognized-model", "unrecognized-model")
] { assert(shortModelName(raw) == visible, "Unexpected label for \(raw)") }
print("Provider, legacy state/cache compatibility, model labels and duration formatting passed")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-presentation-') as directory:
    folder = Path(directory)
    source = folder / 'main.swift'
    source.write_text('import Foundation\nimport SwiftUI\n' +
                      (root / 'Shared/ClaudeBrandColor.swift').read_text() +
                      (root / 'Shared/ClaudeStatus.swift').read_text() + state + widget + clock + harness)
    subprocess.run(['swiftc', str(source), '-o', str(folder / 'tests')], check=True)
    subprocess.run([str(folder / 'tests')], check=True)
