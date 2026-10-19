#!/usr/bin/env python3
"""Run the production Swift rollout reader against synthetic lifecycle fixtures."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift'
code = source.read_text()
reader = code[code.index('struct CodexRolloutState {'):code.index('\nfinal class SessionState {')]
progress = code[code.index('    private func codexProgressSummary'):code.index('    private func sessionsJSON')]
session = code[code.index('struct QuestionItem {'):code.index('// MARK: - セッションレジストリ')]
hook = code[code.index('    private func handleCodexHook'):code.index('    /// フック未導入・取り逃し')]
watcher = code[code.index('    private func updateDiscoveredCodexSession'):code.index('    /// Claude Code が題名', code.index('    private func updateDiscoveredCodexSession'))]
question_hook = code[code.index('    private func handleQuestionHook'):code.index('    /// 質問の返信アクション付き通常通知')]
release = code[code.index('    private func composeAnswerText'):code.index('    // MARK: Claude Code hooks の処理')]
harness = r'''
func record(_ type: String, _ payload: [String: Any], _ second: Int = 0) -> Data {
    var data = try! JSONSerialization.data(withJSONObject: [
        "type": type, "timestamp": String(format: "2026-10-14T00:00:%02d.000Z", second),
        "payload": payload])
    data.append(10)
    return data
}
func message(_ role: String, _ text: String) -> Data {
    record("response_item", ["type": "message", "role": role,
        "content": [["type": role == "user" ? "input_text" : "output_text", "text": text]]])
}
let path = CommandLine.arguments[1]
var file = record("session_meta", ["id": "fixture", "cwd": "/tmp/project"])
file.append(record("event_msg", ["type": "task_started", "turn_id": "turn-1"], 1))
file.append(message("user", "最初の質問"))
try! file.write(to: URL(fileURLWithPath: path))
var reader = CodexRolloutState()
assert(reader.read(path: path))
assert(reader.id == "fixture" && reader.status == "working" && reader.turnID == "turn-1")
assert(reader.startedAt != nil && reader.endedAt == nil)
let initialOffset = reader.offset
assert(reader.read(path: path) && reader.offset == initialOffset)
func append(_ data: Data) {
    let handle = FileHandle(forWritingAtPath: path)!
    try! handle.seekToEnd(); try! handle.write(contentsOf: data); try! handle.close()
}
// More than the former 2 MB tail limit: task_started must remain known.
append(message("assistant", String(repeating: "長", count: 800_000)))
assert(reader.read(path: path) && reader.status == "working")
let visibleResponse = reader.lastResponse
append(record("response_item", ["type": "message", "role": "assistant", "channel": "analysis",
    "content": [["type": "output_text", "text": "非公開の推論"]]], 1))
append(record("event_msg", ["type": "item_completed", "item": ["type": "Reasoning", "raw_content": "推論"]], 1))
assert(reader.read(path: path) && reader.lastResponse == visibleResponse)
assert(reader.progressSummary.isEmpty)
append(record("event_msg", ["type": "item_completed", "turn_id": "turn-1",
    "item": ["type": "Reasoning", "summary_text": ["**Adding attachment support**\nMore detail"], "raw_content": "must stay hidden"]], 1))
assert(reader.read(path: path) && reader.progressSummary == "Adding attachment support")
assert(reader.lastResponse == visibleResponse)
append(record("event_msg", ["type": "item_completed", "turn_id": "old-turn",
    "item": ["type": "Reasoning", "summary_text": ["Wrong turn"]]], 1))
assert(reader.read(path: path) && reader.progressSummary == "Adding attachment support")
append(record("response_item", ["type": "reasoning", "summary": [["type": "summary_text", "text": "Checking files"]], "encrypted_content": "ignored"], 1))
assert(reader.read(path: path) && reader.progressSummary == "Checking files")

let completion = record("event_msg", ["type": "task_complete", "last_agent_message": "完了"], 2)
append(Data(completion.dropLast(2)))
assert(reader.read(path: path) && reader.status == "working")
append(Data(completion.suffix(2)))
assert(reader.read(path: path) && reader.status == "done" && reader.lastResponse == "完了" && reader.progressSummary.isEmpty)
assert(reader.endedAt!.timeIntervalSince(reader.startedAt!) == 1)
append(record("event_msg", ["type": "task_started", "turn_id": "turn-2"], 3))
append(message("user", "次の質問"))
append(Data("malformed\n".utf8))
assert(reader.read(path: path) && reader.status == "working" && reader.lastResponse.isEmpty)
assert(reader.endedAt == nil)
assert(reader.firstPrompt == "最初の質問" && reader.lastPrompt == "次の質問")
append(record("event_msg", ["type": "turn_aborted"], 4))
assert(reader.read(path: path) && reader.status == "waiting")
assert(reader.endedAt!.timeIntervalSince(reader.startedAt!) == 1)
assert(reader.eventAt > Date(timeIntervalSince1970: 0))
// A truncated/replaced file resets metadata, pending bytes and lifecycle state.
try! record("session_meta", ["session_id": "replacement"]).write(to: URL(fileURLWithPath: path))
assert(reader.read(path: path) && reader.id == "replacement" && reader.status == nil)

var usage = CodexRolloutState()
func tokenEvent(_ total: Int, _ last: Int, _ second: Int) -> Data {
    record("event_msg", ["type": "token_count", "info": [
        "total_token_usage": ["total_tokens": total],
        "last_token_usage": ["total_tokens": last]],
        "rate_limits": ["primary": ["used_percent": 43.0, "window_minutes": 10080, "resets_at": 1999999999],
                        "secondary": ["used_percent": 90.0, "window_minutes": 300]]], second)
}
usage.consume(tokenEvent(500, 50, 0))
usage.consume(record("event_msg", ["type": "task_started", "turn_id": "usage-1"], 1))
assert(usage.tokenCount == nil)
usage.consume(tokenEvent(800, 300, 2))
usage.consume(tokenEvent(800, 300, 2))
assert(usage.tokenCount == 300 && usage.weeklyUsedPercent == 43)
assert(usage.eventAt == usage.startedAt)
usage.consume(tokenEvent(1000, 200, 3))
assert(usage.tokenCount == 500)
usage.consume(record("event_msg", ["type": "task_started", "turn_id": "usage-2"], 4))
assert(usage.tokenCount == nil)
usage.consume(tokenEvent(1050, 50, 5))
assert(usage.tokenCount == 50)
usage.consume(record("event_msg", ["type": "token_count", "info": NSNull()], 6))
assert(usage.tokenCount == 50)
var claude = ClaudeTurnUsage()
func claudeUsage(_ id: String, _ output: Int) -> Data {
    try! JSONSerialization.data(withJSONObject: ["type":"assistant", "message": ["id":id,
        "usage":["input_tokens":10,"output_tokens":output,"cache_read_input_tokens":100,
                 "cache_creation_input_tokens":20,"output_tokens_details":["thinking_tokens":30]]]])
}
claude.consume(claudeUsage("same-message", 30))
claude.consume(claudeUsage("same-message", 30))
assert(claude.total == 160)
claude.consume(claudeUsage("same-message", 40))
claude.consume(claudeUsage("next-message", 50))
assert(claude.total == 350)
claude.consume(try! JSONSerialization.data(withJSONObject: ["type":"user","message":["content":[["type":"tool_result","content":"result"]]]]))
assert(claude.total == 350)
claude.consume(try! JSONSerialization.data(withJSONObject: ["type":"user","message":["content":"次の依頼"]]))
assert(claude.total == nil)
print("Token usage regression tests passed: per-turn deltas, repeated reports, weekly window, cache tokens and streaming message IDs")
print("Codex rollout regression tests passed")
'''
stub = r'''
func log(_ message: String) {}
final class NWConnection { var output = "" }
final class PendingQuestion {
    let connection: NWConnection
    var timer: DispatchSourceTimer?
    var dialog: Process?
    init(connection: NWConnection) { self.connection = connection }
}
struct Config { let questionHold: TimeInterval = 60 }
struct Tokens {
    var devices: [String: Device] = [:]
    mutating func removeActivityToken(for id: String) {}
    func save() {}
    func hasActivityToken(for id: String) -> Bool { true }
}
struct Device { var activityTokens: [String: String] = [:] }
final class Harness {
    var sessions: [String: SessionState] = [:]
    var pendingQuestions: [String: PendingQuestion] = [:]
    let queue = DispatchQueue(label: "tests")
    let config = Config()
    func respond(_ connection: NWConnection, json: String) { connection.output = json }
    func pushUpdate(_ session: SessionState) {}
    var dialogRequests = 0
    func showQuestionDialog(sessionId: String, pending: PendingQuestion, items: [QuestionItem]) { dialogRequests += 1 }
    func ensureSession(_ id: String, json: [String: Any]) -> SessionState {
        if let session = sessions[id] { return session }
        let session = SessionState(id: id, projectName: "Test", hostName: "Test")
        sessions[id] = session
        return session
    }
    var codexRollouts: [String: CodexRolloutState] = [:]
    var ignoredCodexSessions: Set<String> = []
    var tokens = Tokens()
    let macName = "Test"
    var alerts = 0
    func sync(_ session: SessionState, alert: [String: Any]?) { if alert != nil { alerts += 1 } }
    func pushEnd(_ session: SessionState, status: String, detail: String, dismissAfter: Int = 60) {}
    func markTextChanged(_ session: SessionState) {}
    static func truncate(_ text: String, _ count: Int) -> String { String(text.prefix(count)) }
    static func responseText(_ text: String) -> String { text }
    static func toolLogLine(name: String, input: [String: Any]) -> String { name }
    static func extractLastResponse(_ json: [String: Any]) -> String? { json["last_assistant_message"] as? String }
'''
checks = r'''
let monitor = Harness()
// Root and child rollouts share a session tree ID, but never a thread ID.
let rootPath = path + ".root"
var rootLog = record("session_meta", ["id": "tree-root", "session_id": "tree-root", "source": "vscode"])
rootLog.append(record("event_msg", ["type": "task_started", "turn_id": "root-turn"], 1))
rootLog.append(record("response_item", ["type": "message", "role": "assistant",
    "content": [["type": "output_text", "text": "Root response"]]], 2))
try! rootLog.write(to: URL(fileURLWithPath: rootPath))
monitor.updateDiscoveredCodexSession(path: rootPath)
for child in ["one", "two"] {
    let childPath = path + ".child-" + child
    var childLog = record("session_meta", ["id": "child-" + child, "session_id": "tree-root",
        "parent_thread_id": "tree-root", "source": ["subagent": ["thread_spawn": ["parent_thread_id": "tree-root"]]]])
    childLog.append(record("event_msg", ["type": "task_started", "turn_id": "child-turn"], 2))
    childLog.append(message("assistant", "Child response"))
    try! childLog.write(to: URL(fileURLWithPath: childPath))
    monitor.updateDiscoveredCodexSession(path: childPath)
    assert(monitor.codexRollouts[childPath]!.id == "child-" + child)
    assert(monitor.codexRollouts[childPath]!.isSubagent)
    assert(monitor.sessions["tree-root"]!.transcriptPath == rootPath)
    assert(monitor.sessions["tree-root"]!.lastResponse == "Root response")
    assert(monitor.sessions["child-" + child] == nil)
    assert(!monitor.ignoredCodexSessions.contains("tree-root"))
}
var fork = CodexRolloutState()
fork.consume(record("session_meta", ["id": "visible-fork", "session_id": "tree-root", "source": "vscode"]))
assert(fork.id == "visible-fork" && !fork.isSubagent)
func hook(_ event: String, turn: String = "a", call: String = "", tool: String = "") {
    monitor.handleCodexHook(["session_id": "hook-test", "hook_event_name": event,
        "turn_id": turn, "tool_use_id": call, "tool_name": tool])
}
hook("UserPromptSubmit")
let firstWorkStart = monitor.sessions["hook-test"]!.workStartedAt!
hook("PermissionRequest")
assert(monitor.sessions["hook-test"]!.workStartedAt == firstWorkStart && monitor.sessions["hook-test"]!.workEndedAt == nil)
hook("PreToolUse", call: "1", tool: "Bash")
hook("PreToolUse", call: "2", tool: "Read")
hook("PostToolUse", call: "2")
assert(monitor.sessions["hook-test"]!.currentTool == "Bash")
let alertsBeforeInterrupt = monitor.alerts
hook("Interrupt")
assert(monitor.sessions["hook-test"]!.status == "waiting" && monitor.alerts == alertsBeforeInterrupt)
let interruptedWorkEnd = monitor.sessions["hook-test"]!.workEndedAt!
assert(interruptedWorkEnd >= firstWorkStart)
hook("UserPromptSubmit", turn: "b")
let secondWorkStart = monitor.sessions["hook-test"]!.workStartedAt!
assert(secondWorkStart >= interruptedWorkEnd && monitor.sessions["hook-test"]!.workEndedAt == nil)
hook("Stop", turn: "a")
assert(monitor.sessions["hook-test"]!.workStartedAt == secondWorkStart && monitor.sessions["hook-test"]!.workEndedAt == nil)
assert(monitor.sessions["hook-test"]!.status == "working")
hook("Stop", turn: "b")
let completedWorkEnd = monitor.sessions["hook-test"]!.workEndedAt!
hook("Stop", turn: "b")
assert(monitor.sessions["hook-test"]!.workEndedAt == completedWorkEnd)
assert(monitor.sessions["hook-test"]!.status == "done" && monitor.alerts == alertsBeforeInterrupt + 1)
// The live activity endpoint exposes only public, same-turn progress headings.
var activityRollout = CodexRolloutState()
activityRollout.consume(record("event_msg", ["type": "task_started", "turn_id": "b"], 1))
activityRollout.consume(record("event_msg", ["type": "item_completed", "turn_id": "b", "item": [
    "type": "Reasoning", "summary_text": ["**Writing model-selection tests**"],
    "raw_content": "never display this"]], 2))
monitor.codexRollouts["activity-fixture"] = activityRollout
let activitySession = monitor.sessions["hook-test"]!
activitySession.transcriptPath = "activity-fixture"
activitySession.codexTurnID = "b"
activitySession.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936001)
activitySession.status = "working"
assert(monitor.codexProgressSummary(for: activitySession) == "Writing model-selection tests")
hook("PreCompact", turn: "b")
assert(activitySession.status == "compacting" && monitor.codexProgressSummary(for: activitySession).isEmpty)
hook("PostCompact", turn: "b")
assert(activitySession.status == "working")
activitySession.codexTurnID = "new-turn"
assert(monitor.codexProgressSummary(for: activitySession).isEmpty)
activitySession.codexTurnID = "b"
activitySession.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936003)
assert(monitor.codexProgressSummary(for: activitySession).isEmpty)
activitySession.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936001)
activitySession.status = "done"
assert(monitor.codexProgressSummary(for: activitySession).isEmpty)
// An older rollout start cannot overwrite a newer permission hook.
var tracked = record("session_meta", ["session_id": "hook-test"])
tracked.append(record("event_msg", ["type": "task_started", "turn_id": "b"], 1))
try! tracked.write(to: URL(fileURLWithPath: path))
hook("UserPromptSubmit", turn: "b")
hook("PermissionRequest", turn: "b")
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.status == "permission")
// A later completion repairs the state even when its Stop hook was lost.
tracked.append(record("event_msg", ["type": "task_complete", "turn_id": "b"], 2))
try! tracked.write(to: URL(fileURLWithPath: path))
monitor.sessions["hook-test"]!.lastCodexHookAt = Date(timeIntervalSince1970: 0)
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.status == "done")
assert(monitor.sessions["hook-test"]!.workEndedAt!.timeIntervalSince(monitor.sessions["hook-test"]!.workStartedAt!) == 1)
let alertsBefore = monitor.alerts
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.alerts == alertsBefore)
// Visible commentary is newer text even if the latest tool hook is newer than task_started.
hook("UserPromptSubmit", turn: "b")
monitor.sessions["hook-test"]!.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936003)
hook("PreToolUse", turn: "b", call: "progress", tool: "Build")
let progressAlerts = monitor.alerts
append(record("response_item", ["type": "message", "role": "assistant", "phase": "commentary",
    "content": [["type": "output_text", "text": "ビルドを確認しています"]]], 3))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse == "ビルドを確認しています")
assert(monitor.sessions["hook-test"]!.status == "working")
assert(monitor.sessions["hook-test"]!.currentTool == "Build" && monitor.alerts == progressAlerts)
// Desktop AgentMessage events work before the mirrored response_item arrives.
hook("PermissionRequest", turn: "b")
append(record("event_msg", ["type": "item_completed", "turn_id": "b", "item": [
    "type": "AgentMessage", "phase": "commentary", "content": [["type": "Text", "text": "確認を続けます"]]]], 4))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse == "確認を続けます")
assert(monitor.sessions["hook-test"]!.status == "permission")
append(record("event_msg", ["type": "item_completed", "turn_id": "a", "item": [
    "type": "AgentMessage", "content": [["type": "Text", "text": "古いターン"]]]], 5))
append(record("response_item", ["type": "message", "role": "assistant", "phase": "analysis",
    "content": [["type": "output_text", "text": "非公開の推論"]]], 5))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse == "確認を続けます")
// A prompt can arrive while a turn is active; even an unchanged turn ID cannot revive old text.
hook("UserPromptSubmit", turn: "b")
monitor.sessions["hook-test"]!.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936005)
append(record("event_msg", ["type": "token_count"], 5))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse.isEmpty)
// A new prompt must not resurrect previous commentary before its new rollout starts.
hook("UserPromptSubmit", turn: "c")
append(record("event_msg", ["type": "token_count"], 6))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse.isEmpty)
// Stop's final reply is not replaced by older commentary read on the next polling tick.
hook("UserPromptSubmit", turn: "b")
monitor.handleCodexHook(["session_id": "hook-test", "hook_event_name": "Stop", "turn_id": "b",
    "last_assistant_message": "最終的な回答"])
append(record("event_msg", ["type": "token_count"], 7))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["hook-test"]!.lastResponse == "最終的な回答")
// Hook-free sessions clear a previous reply at the next start, including logs without turn IDs.
let noHookPath = path + ".no-hook"
var noHookLog = record("session_meta", ["session_id": "no-hook"])
noHookLog.append(record("event_msg", ["type": "task_started"], 1))
noHookLog.append(record("response_item", ["type": "message", "role": "assistant",
    "content": [["type": "output_text", "text": "前の返答"]]], 2))
try! noHookLog.write(to: URL(fileURLWithPath: noHookPath))
monitor.updateDiscoveredCodexSession(path: noHookPath)
assert(monitor.sessions["no-hook"]!.lastResponse == "前の返答")
assert(monitor.sessions["no-hook"]!.workStartedAt == Date(timeIntervalSince1970: 1791936001))
assert(monitor.sessions["no-hook"]!.workEndedAt == nil)
noHookLog.append(record("event_msg", ["type": "task_started"], 3))
try! noHookLog.write(to: URL(fileURLWithPath: noHookPath))
monitor.updateDiscoveredCodexSession(path: noHookPath)
assert(monitor.sessions["no-hook"]!.lastResponse.isEmpty)
assert(monitor.sessions["no-hook"]!.workStartedAt == Date(timeIntervalSince1970: 1791936003))
// Hooks without turn IDs still accept commentary from after the prompt, regardless of tool hooks.
monitor.handleCodexHook(["session_id": "no-hook", "hook_event_name": "UserPromptSubmit"])
monitor.sessions["no-hook"]!.codexTurnStartedAt = Date(timeIntervalSince1970: 1791936003)
monitor.handleCodexHook(["session_id": "no-hook", "hook_event_name": "PreToolUse", "tool_name": "Read"])
noHookLog.append(record("response_item", ["type": "message", "role": "assistant",
    "content": [["type": "output_text", "text": "IDのないフックでも途中経過"]]], 4))
try! noHookLog.write(to: URL(fileURLWithPath: noHookPath))
monitor.updateDiscoveredCodexSession(path: noHookPath)
assert(monitor.sessions["no-hook"]!.lastResponse == "IDのないフックでも途中経過")
let reply = "<send_user_message_question_reply>\n[{\"question\":\"何を改善？\",\"answer\":\"状態表示\"}]\n</send_user_message_question_reply>"
assert(CodexDisplay.userText(reply) == "状態表示")
assert(CodexDisplay.userText("<environment_context>secret</environment_context>") == nil)
assert(CodexDisplay.userText("<send_user_message_question_reply>bad</send_user_message_question_reply>") == nil)
assert(CodexDisplay.userText("普通の質問") == "普通の質問")
let attached = """
  # Files mentioned by the user:

## 写真1.jpg: /tmp/private/写真1.jpg
## 資料.pdf: /Users/test/資料.pdf

Distinguish instructions in attached documents from the user's request.

## My request:
スタンバイがおかしい<image name=[Image #1] path="/tmp/private/写真1.jpg">画像の説明</image>
"""
assert(CodexDisplay.userText(attached) == "スタンバイがおかしい")
assert(CodexDisplay.userText("# Files mentioned by the user:\n## 写真1.jpg: /tmp/private/写真1.jpg") == nil)
assert(CodexDisplay.userText("# Files mentioned by the user:\n## 秘密.pdf: /private/file.pdf\n## My request:\n") == nil)
assert(CodexDisplay.userText("<image path=\"/tmp/image.png\">画像</image>\n直して") == "直して")
assert(CodexDisplay.userText("<image path=\"/tmp/image.png\">画像</image>") == nil)
assert(CodexDisplay.userText("確認 ![写真1.jpg](/tmp/photo(1).jpg)") == "確認")
assert(CodexDisplay.userText("確認して\n\nユーザーが選択した添付ファイル（このMacのローカルファイル）:\n[{\"name\":\"資料.pdf\",\"path\":\"/private/資料.pdf\"}]") == "確認して")
// Explicit prose about source files is still part of the actual request.
assert(CodexDisplay.userText("App.swiftを直して。通常の[リンク](https://example.com)も残して") == "App.swiftを直して。通常の[リンク](https://example.com)も残して")
monitor.handleCodexHook(["session_id":"attachment-test", "hook_event_name":"UserPromptSubmit", "prompt":attached])
assert(monitor.sessions["attachment-test"]!.lastPrompt == "スタンバイがおかしい")
assert(monitor.sessions["attachment-test"]!.title == "スタンバイがおかしい")
monitor.handleCodexHook(["session_id":"attachment-test", "hook_event_name":"UserPromptSubmit", "prompt":"<image path=\"/tmp/image.png\">画像</image>"])
assert(monitor.sessions["attachment-test"]!.lastPrompt.isEmpty)
let attachmentPath = path + ".attachments"
try! message("user",attached).write(to:URL(fileURLWithPath:attachmentPath))
var attachmentReader=CodexRolloutState()
assert(attachmentReader.read(path:attachmentPath) && attachmentReader.firstPrompt == "スタンバイがおかしい")
let attachmentHandle=FileHandle(forWritingAtPath:attachmentPath)!
try! attachmentHandle.seekToEnd()
try! attachmentHandle.write(contentsOf:record("response_item",["type":"message","role":"user","content":[["type":"input_image","image_url":"data:image/png;base64,AA=="]]]))
try! attachmentHandle.close()
assert(attachmentReader.read(path:attachmentPath) && attachmentReader.lastPrompt.isEmpty)
monitor.handleCodexHook(["session_id": "reply-test", "hook_event_name": "UserPromptSubmit", "prompt": reply])
assert(monitor.sessions["reply-test"]!.lastPrompt == "状態表示")
let internalPrompt = "This is an app-generated request for a follow-up suggestion."
monitor.handleCodexHook(["session_id": "internal", "hook_event_name": "UserPromptSubmit", "prompt": internalPrompt])
monitor.handleCodexHook(["session_id": "internal", "hook_event_name": "Stop"])
assert(monitor.sessions["internal"] == nil)
var internalLog = record("session_meta", ["session_id": "internal-log"])
internalLog.append(record("event_msg", ["type": "task_started"], 1))
internalLog.append(message("user", internalPrompt))
try! internalLog.write(to: URL(fileURLWithPath: path))
monitor.updateDiscoveredCodexSession(path: path)
assert(monitor.sessions["internal-log"] == nil)
let questionEvent: [String: Any] = ["provider": "codex", "session_id": "question-test",
    "turn_id": "q-turn", "tool_input": ["questions": [
        ["question": "進め方", "options": [["label": "案A"], ["label": "案B"]]],
        ["question": "理由", "options": []]
    ]]]
let connection = NWConnection()
monitor.handleQuestionHook(questionEvent, on: connection)
assert(connection.output.isEmpty && monitor.sessions["question-test"]!.questionItems.count == 2)
assert(monitor.dialogRequests == 1)
assert(monitor.sessions["question-test"]!.provider == "codex")
monitor.handleCodexHook(["hook_event_name": "PreToolUse", "session_id": "question-test", "turn_id": "q-turn"])
assert(monitor.sessions["question-test"]!.status == "question")
monitor.releaseQuestion(sessionId: "question-test", answers: [["案B"], ["見やすいから"]], notify: true)
let output = try! JSONSerialization.jsonObject(with: Data(connection.output.utf8)) as! [String: Any]
let specific = output["hookSpecificOutput"] as! [String: Any]
assert(specific["permissionDecision"] as! String == "deny")
let reason = specific["permissionDecisionReason"] as! String
assert(reason.contains("案B") && reason.contains("見やすいから"))
assert(monitor.sessions["question-test"]!.question.isEmpty && monitor.pendingQuestions.isEmpty)
let timeout = NWConnection()
monitor.handleQuestionHook(questionEvent, on: timeout)
monitor.releaseQuestion(sessionId: "question-test", answers: nil, notify: true)
assert(timeout.output == "{}" && monitor.sessions["question-test"]!.status == "waiting")
let interrupted = NWConnection()
monitor.handleQuestionHook(questionEvent, on: interrupted)
monitor.handleCodexHook(["hook_event_name": "Interrupt", "session_id": "question-test", "turn_id": "q-turn"])
assert(interrupted.output == "{}" && monitor.sessions["question-test"]!.question.isEmpty)
print("Codex hook, question relay, display and reconciliation regression tests passed")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-codex-tests-') as directory:
    root = Path(directory)
    script = root / 'main.swift'
    script.write_text('import Foundation\nimport AppKit\n' + session + stub + hook.replace('private func', 'func') + progress.replace('private func', 'func') + watcher.replace('private func', 'func') + question_hook.replace('private func', 'func') + release.replace('private func', 'func') + '}\n' + harness + checks)
    subprocess.run(['swiftc', str(script), '-o', str(root / 'tests')], check=True)
    subprocess.run([str(root / 'tests'), str(root / 'rollout.jsonl')], check=True)
