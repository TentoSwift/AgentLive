"""Exercise production RPC against an isolated Codex home, never user queues."""
from pathlib import Path
import struct,zlib,json,os,select,sqlite3,subprocess,tempfile,time,uuid
source=(Path(__file__).resolve().parents[1]/'ClaudeLiveDaemon.swift').read_text()
code=source[source.index('final class NotchCodexQueueRPC {'):source.index('// MARK: - デーモン本体')]
code=code.replace('throw NotchCodexIPC.Failure.rejected("queue_request_failed")', 'throw NotchCodexIPC.Failure.rejected("\\(method): \\(response[\"error\"] ?? \"unknown\")")')
cli='/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'
with tempfile.TemporaryDirectory(dir='/tmp',prefix='notch-queue-') as tmp:
 root=Path(tmp);env=dict(os.environ,CODEX_HOME=tmp,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
 thread=str(uuid.uuid4());qid=str(uuid.uuid4());client=str(uuid.uuid4())
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
 image=root/'fixture.png';image.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff'))+chunk(b'IEND',b''))
 p=subprocess.Popen([cli,'app-server','--stdio'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
 buffer=b''
 def req(id,method,params):
  global buffer
  p.stdin.write((json.dumps(dict(id=id,method=method,params=params))+'\n').encode());p.stdin.flush();deadline=time.monotonic()+6
  while time.monotonic()<deadline:
   if b'\n' in buffer:
    line,buffer=buffer.split(b'\n',1);r=json.loads(line)
    if r.get('id')==id:return r
   elif select.select([p.stdout],[],[],1)[0]:buffer+=os.read(p.stdout.fileno(),65536)
  raise TimeoutError()
 try:
  assert 'result' in req(1,'initialize',{'clientInfo':{'name':'notch_tests','version':'1.0'},'capabilities':{'experimentalApi':True}})
  p.stdin.write(b'{"method":"initialized"}\n');p.stdin.flush()
  rollout=root/'fixture.jsonl'
  rollout.write_text(json.dumps({'type':'session_meta','timestamp':'2026-10-16T00:00:00Z','payload':{'id':thread,'timestamp':'2026-10-16T00:00:00Z','cwd':tmp,'runtime_workspace_roots':[tmp],'history_mode':'legacy','originator':'codex_cli_rs','cli_version':'0.0.0','source':'cli','model_provider':'openai'}})+'\n')
  state=sqlite3.connect(root/'state_5.sqlite')
  state.execute('insert into threads(id,rollout_path,created_at,updated_at,source,model_provider,cwd,title,sandbox_policy,approval_mode) values(?,?,?,?,?,?,?,?,?,?)',(thread,str(rollout),1,1,'cli','openai',tmp,'Disposable test','{"type":"read-only"}','never'));state.commit();state.close()
  result=req(2,'thread/queue/list' ,{'threadId':thread});assert 'result' in result,result
 finally:p.terminate();p.wait(timeout=3)
 db=sqlite3.connect(root/'queue_1.sqlite')
 payload={'UserInput':{'content':[{'type':'text','text':'before','text_elements':[]},{'type':'local_image','path':str(image)}],'client_id':client}}
 db.execute('insert into queued_items values(?,?,?,?,?,?)',(qid,thread,json.dumps(payload),1,1,1));db.commit();db.close()
 fixture=r'''
enum NotchCodexIPC { enum Failure: Error { case unavailable, protocolError, rejected(String) } }
let thread = CommandLine.arguments[1], id = CommandLine.arguments[2], client = CommandLine.arguments[3]
let rpc = try NotchCodexQueueRPC()
let listed = try rpc.request("thread/queue/list", params:["threadId":thread])["data"] as! [[String:Any]]
precondition(listed.count == 1)
let result = try rpc.request("thread/queue/update", params:["threadId":thread, "queuedSubmissionId":id,
 "input":[["type":"text","text":"after","text_elements":[]],["type":"localImage","path":CommandLine.arguments[4]]]])
let item = result["queuedSubmission"] as! [String:Any]
precondition(item["id"] as? String == id && item["clientUserMessageId"] as? String == client)
precondition((item["input"] as! [[String:Any]]).count == 2)
precondition(try! rpc.request("thread/queue/delete",params:["threadId":thread,"queuedSubmissionId":id])["deleted"] as? Bool == true)
precondition(try! (rpc.request("thread/queue/list",params:["threadId":thread])["data"] as! [[String:Any]]).isEmpty)
let imageRequest = UUID().uuidString
try rpc.enqueueImages(sessionId: thread, text: "image prompt", imagePaths: [CommandLine.arguments[4]], requestId: imageRequest)
let added = try rpc.request("thread/queue/list", params: ["threadId": thread])["data"] as! [[String:Any]]
precondition(added.count == 1)
precondition(added[0]["clientUserMessageId"] as? String == imageRequest)
let content = added[0]["input"] as! [[String:Any]]
precondition(content.count == 2 && content[1]["type"] as? String == "image")
let imageURL = content[1]["url"] as! String
precondition(imageURL.hasPrefix("data:image/png;base64,"))
precondition(Data(base64Encoded: String(imageURL.split(separator: ",", maxSplits: 1)[1])) == (try! Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[4]))))
print("PASS: real Codex queue API in isolated home, edit preserves ID/client/attachment, delete removes only selected item; image enqueue preserves actual image bytes")
'''
 (root/'main.swift').write_text('import Foundation\nimport Darwin\n'+code+fixture)
 subprocess.run(['xcrun','swiftc',str(root/'main.swift'),'-o',str(root/'check')],env=env,check=True)
 subprocess.run([str(root/'check'),thread,qid,client,str(image)],env=env,check=True,timeout=20)
