"""Verify queue reads against disposable SQLite databases, never the live queue."""
from pathlib import Path
import json, os, sqlite3, subprocess, tempfile
source = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
code = source[source.index('enum CodexPendingQueue {'):source.index('/// Local Codex history metadata;')]
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    db = root / 'queue.sqlite'
    connection = sqlite3.connect(db)
    connection.execute('create table queued_items(id text primary key, thread_id text, payload_json text, queue_order integer, created_at_ms integer)')
    def insert(id, thread, text, order, extras=[]):
        connection.execute('insert into queued_items values(?,?,?,?,?)', (id, thread, json.dumps({'UserInput': {'content': [{'type':'text','text':text}] + extras}}), order, order))
    insert('second', 'thread-A', '同じ文', 2)
    insert('first', 'thread-A', '同じ文', 1)
    insert('foreign', 'thread-B', '別セッション', 0)
    insert('photo', 'thread-A', '', 3, [{'type':'localImage','path':'/private/test/photo.png'}])
    connection.commit()
    fixture = r'''
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let rows = CodexPendingQueue.read(sessionId: "thread-A", databaseURL: url)!
precondition(rows.map { $0["id"] as! String } == ["first", "second", "photo"])
precondition(rows[2]["attachments"] as! [String] == ["photo.png"])
precondition(CodexPendingQueue.read(sessionId: "missing", databaseURL: url)!.isEmpty)
precondition(CodexPendingQueue.read(sessionId: "' OR 1=1 --", databaseURL: url)!.isEmpty)
precondition(CodexPendingQueue.read(sessionId: "thread-A", databaseURL: url.appendingPathExtension("missing")) == nil)
var db: OpaquePointer?
precondition(sqlite3_open(url.path, &db) == SQLITE_OK)
sqlite3_exec(db, "DELETE FROM queued_items WHERE id='first'", nil, nil, nil)
precondition(CodexPendingQueue.read(sessionId: "thread-A", databaseURL: url)!.count == 2)
sqlite3_exec(db, "UPDATE queued_items SET payload_json='invalid' WHERE id='second'", nil, nil, nil)
precondition(CodexPendingQueue.read(sessionId: "thread-A", databaseURL: url) == nil)
sqlite3_exec(db, "DROP TABLE queued_items", nil, nil, nil)
precondition(CodexPendingQueue.read(sessionId: "thread-A", databaseURL: url) == nil)
sqlite3_close(db)
print("PASS: queue ordering, duplicate text IDs, session isolation, attachments, dequeue, missing DB and unsupported/corrupt schema")
'''
    swift = root / 'main.swift'
    swift.write_text('import Foundation\nimport SQLite3\n' + code + fixture)
    env = dict(os.environ, DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
    subprocess.run(['xcrun', 'swiftc', str(swift), '-o', str(root / 'checks')], env=env, check=True)
    subprocess.run([str(root / 'checks'), str(db)], check=True)
