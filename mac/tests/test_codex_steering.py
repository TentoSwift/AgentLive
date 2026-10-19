"""Exercise production IPC with a local fake desktop; never steer a real chat."""
from pathlib import Path
import json,os,socket,struct,subprocess,tempfile,threading
s=(Path(__file__).resolve().parents[1]/'ClaudeLiveDaemon.swift').read_text()
code=s[s.index('final class NotchCodexIPC {'):s.index('/// Queue mutations use Codex')]
with tempfile.TemporaryDirectory(dir='/tmp',prefix='notch-ipc-') as tmp:
 root=Path(tmp);path=str(root/'test.sock');server=socket.socket(socket.AF_UNIX);server.bind(path);server.listen();failures=[]
 def serve():
  try:
   for scenario in range(4):
    c,_=server.accept();c.settimeout(4)
    def read(n):
     data=b''
     while len(data)<n:
      part=c.recv(n-len(data))
      if not part:raise EOFError()
      data+=part
     return data
    count=3
    for i in range(count):
     request=json.loads(read(struct.unpack('<I',read(4))[0]));method=request['method'];params=request['params']
     reply=dict(type='response',requestId=request['requestId'],method=method,resultType='success')
     if i==0:
      assert method=='initialize';reply['result']={'clientId':'test-client'}
     elif i==1:
      assert method=='thread-owner-discovery';assert params['conversationId']=='test-thread';reply['handledByClientId']='owner';reply['result']={}
     elif i==2:
      assert method=='thread-follower-steer-turn';assert request['targetClientId']=='owner'
      assert params['clientUserMessageId']=='stable-message-id'
      assert params['input'][0]['text']=='修正指示'
      assert isinstance(params['restoreMessage']['context'],dict)
      assert 'model' not in params and 'approvalPolicy' not in params
      reply['result']={'result':{'turnId':'turn-1'}}
      if scenario==2:reply.update(resultType='error',error='no active turn to steer')
     else:
      assert method=='thread-follower-remove-queued-message';assert params['messageId']=='queued-1'
      reply['result']={'removed':scenario!=3}
     encoded=json.dumps(reply).encode();frame=struct.pack('<I',len(encoded))+encoded
     c.sendall(frame[:2]);c.sendall(frame[2:])
    c.close()
  except Exception as e:failures.append(e)
  finally:server.close()
 thread=threading.Thread(target=serve,daemon=True);thread.start()
 fixture=r'''
final class NotchCodexQueueRPC {
 static var deleted = true
 static var calls = 0
 func request(_ method: String, params: [String:Any]) throws -> [String:Any] {
  precondition(method == "thread/queue/delete" && params["queuedSubmissionId"] as? String == "queued-1")
  Self.calls += 1
  return ["deleted": Self.deleted]
 }
}
let path = CommandLine.arguments[1]
let input: [[String: Any]] = [["type":"text", "text":"修正指示", "text_elements":[]]]
precondition(try! NotchCodexIPC(socketPath: path).steer(sessionId: "test-thread", input: input, clientMessageId: "stable-message-id"))
precondition(try! NotchCodexIPC(socketPath: path).steer(sessionId: "test-thread", input: input, clientMessageId: "stable-message-id", queuedId: "queued-1"))
do {
 _ = try NotchCodexIPC(socketPath: path).steer(sessionId: "test-thread", input: input, clientMessageId: "stable-message-id")
 preconditionFailure("rejection must not count as delivery")
} catch {}
precondition(NotchCodexQueueRPC.calls == 1)
NotchCodexQueueRPC.deleted = false
precondition(try! !NotchCodexIPC(socketPath: path).steer(sessionId: "test-thread", input: input, clientMessageId: "stable-message-id", queuedId: "queued-1"))
print("PASS: fragmented IPC frames, ownership discovery, direct steering, stable request identity, rejection and acknowledgement-before-queue-removal")
'''
 (root/'main.swift').write_text('import Foundation\nimport Darwin\n'+code+fixture)
 env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
 subprocess.run(['xcrun','swiftc',str(root/'main.swift'),'-o',str(root/'checks')],env=env,check=True)
 subprocess.run([str(root/'checks'),path],check=True,timeout=20)
 thread.join(timeout=3)
 assert not failures,failures
