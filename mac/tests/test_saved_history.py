"""Production history reader: metadata isolation and long paginated transcripts."""
from pathlib import Path
import os,json,sqlite3,subprocess,tempfile,base64,zlib,struct
s=(Path(__file__).resolve().parents[1]/'ClaudeLiveDaemon.swift').read_text()
code=s[s.index('enum CodexSavedHistory {'):s.index('/// Speaks the installed desktop')]
display=s[s.index('enum CodexDisplay {'):s.index('struct CodexRolloutState {')]
messages=s[s.index('    private static func messagesJSON'):s.index('    /// transcript JSONL（')]
messages='enum CodexPendingQueue { static func read(sessionId: String) -> [[String: Any]]? { [] } }\n' + 'enum HistoryEndpoint {\n' + messages.replace('private static func', 'static func') + '\nstatic func parseTranscript(path: String?, includeSidechain: Bool) -> [[String: String]] { [] }\n}\n'
with tempfile.TemporaryDirectory() as tmp:
 r=Path(tmp); db=sqlite3.connect(r/'state.sqlite')
 db.execute('create table threads(id text,title text,name text,cwd text,rollout_path text,archived integer,source text,updated_at integer)')
 for i in range(65):db.execute('insert into threads values(?,?,?,?,?,?,?,?)',(str(i),'題名'+str(i),('保存した名前' if i==64 else ('  ' if i==63 else None)),'/tmp/project',str(r/'rollout.jsonl'),i%2,'vscode',i))
 db.execute('insert into threads values(?,?,?,?,?,?,?,?)',('internal','hidden',None,'','',0,'exec',999));db.commit()
 db.backup(sqlite3.connect(r/'state_5.sqlite'))
 lines=[]
 for i in range(210):
  text=f'発話{i}'+ ('長い文章'*180000 if i==105 else '')
  lines.append(json.dumps({'type':'response_item','payload':{'type':'message','role':'user' if i%2==0 else 'assistant','content':[{'type':'input_text' if i%2==0 else 'output_text','text':text}]}} ,ensure_ascii=False)+'\n')
 (r/'rollout.jsonl').write_text(''.join(lines))
 def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\x00\x00'))+chunk(b'IEND',b'')
 image={'type':'input_image','image_url':'data:image/png;base64,'+base64.b64encode(png).decode()}
 media={'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'# Files mentioned by the user:\n\n## 写真.png: /missing/写真.png\n\n## 資料.pdf: /missing/資料.pdf\n\n## My request:\n確認して'},image]}}
 (r/'media.jsonl').write_text(json.dumps(media,ensure_ascii=False)+'\n')
 # Large embedded screenshots and tool output must not change byte cursors or
 # hide earlier messages. Each spans hundreds of the reader's disk chunks.
 huge_image={'type':'input_image','image_url':'data:image/png;base64,'+'A'*(14*1024*1024)}
 oversized=[
  {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'最初'}]}},
  {'type':'response_item','payload':{'type':'function_call_output','output':'出力'*(3*1024*1024)}},
  {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'画像を確認'},huge_image]}},
  {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'最後'}]}}
 ]
 large_bytes=bytearray(b'\n'); large_offsets=[]
 for item in oversized:
  large_offsets.append(len(large_bytes))
  large_bytes.extend(json.dumps(item,ensure_ascii=False).encode()+b'\n\n')
 (r/'large-lines.jsonl').write_bytes(large_bytes)
 (r/'large-offsets.json').write_text(json.dumps(large_offsets))

 fixture=r'''
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let rows = CodexSavedHistory.rows(databaseURL: root.appendingPathComponent("state.sqlite"))!
precondition(rows.count == 51 && rows[0]["title"] == "保存した名前" && rows[1]["title"] == "題名63")
precondition(!rows.contains { $0["sessionId"] == "internal" })
precondition(CodexSavedHistory.rows(sessionId: "0", databaseURL: root.appendingPathComponent("state.sqlite"))!.first!["title"] == "題名0")
let path = root.appendingPathComponent("rollout.jsonl").path
// A stale hook/watcher path must never replace this thread's canonical history.
let endpoint = HistoryEndpoint.messagesJSON(sessionId: "0", limit: 1, livePath: root.appendingPathComponent("media.jsonl").path,
    liveIsCodex: true, fallbackPath: nil)
let endpointPayload = try JSONSerialization.jsonObject(with: Data(endpoint.utf8)) as! [String: Any]
let endpointMessages = endpointPayload["messages"] as! [[String: Any]]
precondition(endpointMessages.count == 1 && endpointMessages[0]["text"] as? String == "発話209")
var cursor: UInt64? = nil
var all: [[String:Any]] = []
repeat {
 let page = try CodexSavedHistory.page(path: path, before: cursor, limit: 37)
 all = page.messages + all
 if let next = page.cursor, let old = cursor { precondition(next < old) }
 cursor = page.cursor
} while cursor != nil
precondition(all.count == 210)
precondition(Set(all.map { $0["id"] as! String }).count == 210)
for (i, message) in all.enumerated() { precondition((message["text"] as! String).hasPrefix("発話\(i)")) }
precondition((all[105]["text"] as! String).count > 2000)
let first = try CodexSavedHistory.page(path: path, before: nil, limit: 50)
let old = first.cursor!
let handle = FileHandle(forWritingAtPath: path)!; try handle.seekToEnd()
try handle.write(contentsOf: Data("\n{broken".utf8)); try handle.close()
let earlier = try CodexSavedHistory.page(path: path, before: old, limit: 50)
precondition(earlier.messages.last!["text"] as? String == "発話159")
let mediaPath = root.appendingPathComponent("media.jsonl").path
let mediaPage = try CodexSavedHistory.page(path: mediaPath, before: nil, limit: 50)
precondition(mediaPage.messages[0]["text"] as? String == "確認して")
let attachments = mediaPage.messages[0]["attachments"] as! [[String: Any]]
precondition(attachments.count == 2 && attachments[0]["name"] as? String == "写真.png" && attachments[1]["isImage"] as? Bool == false)
precondition(attachments[0]["source"] == nil)
let thumbnail = try CodexSavedHistory.thumbnail(path: mediaPath, offset: 0, index: 0)
precondition(thumbnail != nil && CGImageSourceCreateWithData(thumbnail! as CFData, nil) != nil)
precondition(try! CodexSavedHistory.thumbnail(path: mediaPath, offset: 1, index: 0) == nil)
precondition(try! CodexSavedHistory.thumbnail(path: mediaPath, offset: 0, index: 1) == nil)
precondition(try! CodexSavedHistory.thumbnail(path: mediaPath, offset: 0, index: 999) == nil)
let largePath = root.appendingPathComponent("large-lines.jsonl").path
let offsets = try JSONDecoder().decode([UInt64].self, from: Data(contentsOf: root.appendingPathComponent("large-offsets.json")))
let newestLarge = try CodexSavedHistory.page(path: largePath, before: nil, limit: 2)
precondition(newestLarge.messages.map { $0["text"] as! String } == ["画像を確認", "最後"])
precondition(newestLarge.messages.map { $0["id"] as! String } == [String(offsets[2]), String(offsets[3])])
precondition(newestLarge.cursor == offsets[2])
precondition((newestLarge.messages[0]["attachments"] as! [[String: Any]]).count == 1)
let oldestLarge = try CodexSavedHistory.page(path: largePath, before: newestLarge.cursor, limit: 1)
precondition(oldestLarge.messages.count == 1 && oldestLarge.messages[0]["text"] as? String == "最初")
precondition(oldestLarge.messages[0]["id"] as? String == String(offsets[0]))
precondition(oldestLarge.cursor == offsets[0])
let leadingBlank = try CodexSavedHistory.page(path: largePath, before: oldestLarge.cursor, limit: 1)
precondition(leadingBlank.messages.isEmpty && leadingBlank.cursor == nil)
let emptyLarge = try CodexSavedHistory.page(path: largePath, before: 0, limit: 100)
precondition(emptyLarge.messages.isEmpty && emptyLarge.cursor == nil)
let imageOnly: [String:Any] = ["type":"response_item", "payload":["type":"message","role":"user","content":[["type":"input_image","image_url":"https://invalid.example/image.png"]]]]
let imageMessage = CodexSavedHistory.message(try JSONSerialization.data(withJSONObject: imageOnly), offset: 0)
precondition((imageMessage?["attachments"] as? [[String: Any]])?.count == 1)
for (kind, role) in [("task_started", "workStarted"), ("task_complete", "workEnded"), ("turn_aborted", "workEnded")] {
    let event: [String: Any] = ["type": "event_msg", "timestamp": "2026-10-16T02:03:04Z",
        "payload": ["type": kind, "turn_id": "turn-1", "started_at": 1_792_108_800.0]]
    let timing = CodexSavedHistory.message(try JSONSerialization.data(withJSONObject: event), offset: 42)!
    precondition(timing["role"] as? String == role && timing["turnID"] as? String == "turn-1")
    precondition(timing["id"] as? String == "42")
    if kind == "turn_aborted" { precondition(timing["text"] as? String == "interrupted") }
    if kind != "task_started" { precondition(timing["timestamp"] as? String == "2026-10-16T02:03:04Z") }
}
for event: [String: Any] in [
    ["type": "compacted", "timestamp": "2026-10-16T02:03:04Z", "payload": ["message": "private summary"]],
    ["type": "event_msg", "payload": ["type": "context_compacted"]]
] {
    let row = CodexSavedHistory.message(try JSONSerialization.data(withJSONObject: event), offset: 43)!
    precondition(row["role"] as? String == "compaction")
    precondition(row["text"] as? String == "")
}
print("PASS: embedded image thumbnail after source removal, named files, image-only message, invalid offsets/indexes; saved metadata, internal-session exclusion, 210 messages across >2MB, full long text, stable cursors, no duplicates; large image/tool lines, blank lines and exact byte cursors")
'''
 (r/'main.swift').write_text('import Foundation\nimport SQLite3\nimport ImageIO\n'+display+code+messages+fixture)
 env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
 subprocess.run(['xcrun','swiftc',str(r/'main.swift'),'-o',str(r/'checks')],env=env,check=True)
 subprocess.run([str(r/'checks'),str(r)],env=dict(env,CODEX_HOME=str(r)),check=True)
