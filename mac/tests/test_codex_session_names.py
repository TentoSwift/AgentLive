#!/usr/bin/env python3
"""Exercise metadata-only renames without changing a rollout or work state."""
from pathlib import Path
import os, sqlite3, subprocess, tempfile

source = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
display = source[source.index('enum CodexDisplay {'):source.index('struct CodexRolloutState {')]
history = source[source.index('enum CodexSavedHistory {'):source.index('/// Speaks the installed desktop')]
refresh = source[source.index('    private func refreshCodexSessionNames()'):source.index('    private func updateDiscoveredCodexSession')]
fixture = r'''
final class SessionState {
    let id: String
    var provider = "codex"
    var name = "ClaudeLive"
    var title = "最初の入力"
    var status = "done"
    var lastResponse = "保持する返答"
    var workStartedAt = Date(timeIntervalSince1970: 100)
    var workEndedAt = Date(timeIntervalSince1970: 160)
    init(_ id: String) { self.id = id }
}
final class Harness {
    var sessions = ["0": SessionState("0"), "64": SessionState("64"), "claude": SessionState("claude")]
    var pushes: [String] = []
    func sync(_ session: SessionState, alert: [String: Any]?) {
        precondition(alert == nil, "A rename must not produce a completion notification")
        pushes.append(session.id)
    }
'''
checks = r'''
}
let harness = Harness()
harness.sessions["claude"]!.provider = "claude"
precondition(!CodexSavedHistory.rows()!.contains { $0["sessionId"] == "0" })
precondition(CodexSavedHistory.rows(sessionIDs: [])!.isEmpty)
precondition(CodexSavedHistory.rows(sessionIDs: ["missing"])!.isEmpty)
harness.refreshCodexSessionNames()
let session = harness.sessions["0"]!
precondition(session.name == "AgentLive" && session.title == "AgentLive")
precondition(harness.sessions["64"]!.name == "新しいスレッド")
precondition(harness.sessions["claude"]!.name == "ClaudeLive")
precondition(Set(harness.pushes) == Set(["0", "64"]))
harness.refreshCodexSessionNames()
precondition(harness.pushes.count == 2, "Unchanged metadata must not push again")
var db: OpaquePointer?
precondition(sqlite3_open(CommandLine.arguments[1], &db) == SQLITE_OK)
func update(_ sql: String) { precondition(sqlite3_exec(db, sql, nil, nil, nil) == SQLITE_OK) }
update("UPDATE threads SET name = 'リネーム後' WHERE id = '0'")
harness.refreshCodexSessionNames()
precondition(session.name == "リネーム後" && session.title == "リネーム後")
precondition(harness.pushes.count == 3)
update("UPDATE threads SET name = '  ' WHERE id = '0'")
harness.refreshCodexSessionNames()
precondition(session.name == "元のタイトル" && harness.pushes.count == 4)
update("DROP TABLE threads")
harness.refreshCodexSessionNames()
precondition(session.name == "元のタイトル" && harness.pushes.count == 4)
precondition(session.status == "done" && session.lastResponse == "保持する返答")
precondition(session.workStartedAt == Date(timeIntervalSince1970: 100))
precondition(session.workEndedAt == Date(timeIntervalSince1970: 160))
sqlite3_close(db)
print("PASS: metadata-only rename, older than history page, rename removal, unchanged suppression, DB failure, no alert/work-state changes")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-session-names-') as temp:
    root = Path(temp)
    database = root / 'state_5.sqlite'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE threads(id TEXT,name TEXT,title TEXT,cwd TEXT,rollout_path TEXT,archived INTEGER,source TEXT,updated_at INTEGER)')
        for index in range(65):
            db.execute('INSERT INTO threads VALUES(?,?,?,?,?,?,?,?)', (
                str(index), 'AgentLive' if index == 0 else '新しいスレッド', '元のタイトル',
                '/tmp/project', '/tmp/unchanged.jsonl', 0, 'vscode', index))
    swift = root / 'main.swift'
    swift.write_text('import Foundation\nimport SQLite3\nimport ImageIO\n' + display + history + fixture +
                     refresh.replace('private func', 'func') + checks)
    subprocess.run(['swiftc', str(swift), '-o', str(root / 'checks')], check=True)
    subprocess.run([str(root / 'checks'), str(database)], env=dict(os.environ, CODEX_HOME=temp), check=True)
