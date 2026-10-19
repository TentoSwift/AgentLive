"""Model catalog and owner settings against isolated fake CLI/IPC endpoints."""
from pathlib import Path
import json, os, socket, struct, subprocess, tempfile, threading

source = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
code = source[source.index('enum NotchCodexModelSettings {'):source.index('/// Owns CLI executions started by the notch')]
with tempfile.TemporaryDirectory(prefix='notch-models-') as temporary:
    root = Path(temporary)
    fake = root / 'codex'
    fake.write_text('''#!/usr/bin/python3
import json,sys,pathlib
root=pathlib.Path(__file__).parent
def model(name,efforts,default=False,hidden=False):
 return dict(id=name,model=name,displayName=name.upper(),description='description',hidden=hidden,isDefault=default,defaultReasoningEffort=efforts[0],supportedReasoningEfforts=[dict(reasoningEffort=e,description=e) for e in efforts])
for line in sys.stdin:
 req=json.loads(line)
 if 'id' not in req:continue
 method=req['method'];params=req.get('params',{})
 with (root/'rpc-calls').open('a') as f:f.write(json.dumps(dict(method=method,params=params))+'\\n')
 if method=='initialize':result={}
 elif method=='model/list':
  assert params['includeHidden']==False
  result=dict(data=[model('model-b',['medium','max'])],nextCursor=None) if params.get('cursor')=='page-2' else dict(data=[model('model-a',['low','high'],True),model('hidden',['high'],hidden=True)],nextCursor='page-2')
 elif method=='config/read':result=dict(config=dict(model='model-b',model_reasoning_effort='max'))
 elif method=='thread/read':
  assert params==dict(threadId='closed',includeTurns=False)
  result=dict(thread=dict(model='model-b',reasoningEffort='max'))
 else:raise AssertionError(method)
 print(json.dumps(dict(id=req['id'],result=result)),flush=True)
''')
    fake.chmod(0o700)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    address = str(root / 'ipc.sock')
    server.bind(address); server.listen(8)
    selected = dict(model='model-a', reasoningEffort=None)
    errors = []
    calls = []
    stopped = threading.Event()
    def read_exact(connection, count):
        data = b''
        while len(data) < count:
            chunk = connection.recv(count-len(data))
            if not chunk: raise EOFError
            data += chunk
        return data
    def serve():
        while not stopped.is_set():
            try: connection, _ = server.accept()
            except OSError: break
            try:
                with connection:
                    while True:
                        req = json.loads(read_exact(connection, struct.unpack('<I', read_exact(connection, 4))[0]))
                        calls.append(req)
                        method = req['method']; params = req['params']
                        reply = dict(type='response', requestId=req['requestId'], resultType='success', result={})
                        if method == 'initialize': reply['result'] = dict(clientId='fixture-client')
                        elif method == 'thread-owner-discovery':
                            assert params['hostId'] == 'local'
                            if params['conversationId'] == 'closed': reply['resultType'] = 'error'; reply['error'] = 'owner unavailable'
                            else: reply['handledByClientId'] = 'owner-1'
                        elif method == 'thread-follower-read-model-settings':
                            assert req['version'] == 1 and req['targetClientId'] == 'owner-1'
                            reply['result'] = dict(settings=selected.copy())
                        elif method == 'thread-follower-update-thread-settings':
                            assert req['version'] == 2 and req['targetClientId'] == 'owner-1'
                            assert set(params) == {'conversationId', 'threadSettings'}
                            assert set(params['threadSettings']) == {'model', 'effort'}
                            accepted = params['conversationId'] != 'reject'
                            if accepted: selected.update(model=params['threadSettings']['model'], reasoningEffort=params['threadSettings']['effort'])
                            reply['result'] = dict(applied=accepted)
                        else: raise AssertionError(method)
                        body = json.dumps(reply).encode()
                        connection.sendall(struct.pack('<I', len(body))+body)
            except EOFError: pass
            except Exception as error: errors.append(error)
    thread = threading.Thread(target=serve, daemon=True); thread.start()
    fixture = r'''
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let rpc = try NotchCodexQueueRPC(executable: root.appendingPathComponent("codex").path)
let ipc = { try NotchCodexIPC(socketPath: root.appendingPathComponent("ipc.sock").path) }
let catalog = try NotchCodexModelSettings.catalog(rpc)
precondition(catalog.map { $0["model"] as! String } == ["model-a", "model-b"])
try NotchCodexModelSettings.validate(model: "model-a", effort: "high", models: catalog)
try NotchCodexModelSettings.validate(model: "model-a", effort: nil, models: catalog)
for (model, effort) in [("unknown", "high"), ("model-a", "max")] {
    do { try NotchCodexModelSettings.validate(model: model, effort: effort, models: catalog); preconditionFailure("accepted unsupported selection") } catch {}
}
let initial = try NotchCodexModelSettings.snapshot(rpc: rpc, sessionId: nil, cwd: root.path, ipc: ipc)
precondition(initial["selectedModel"] as? String == "model-b" && initial["selectedReasoningEffort"] as? String == "max")
let live = try NotchCodexModelSettings.snapshot(rpc: rpc, sessionId: "live", cwd: nil, ipc: ipc)
precondition(live["selectedModel"] as? String == "model-a" && live["selectedReasoningEffort"] is NSNull)
precondition(live["canUpdate"] as? Bool == true && live["settingsSource"] as? String == "owner")
let saved = try NotchCodexModelSettings.snapshot(rpc: rpc, sessionId: "closed", cwd: nil, ipc: ipc)
precondition(saved["selectedModel"] as? String == "model-b" && saved["canUpdate"] as? Bool == false)
let changed = try ipc().updateModelSettings(sessionId: "live", model: "model-b", effort: "max")
precondition(changed["model"] as? String == "model-b" && changed["reasoningEffort"] as? String == "max")
let automatic = try ipc().updateModelSettings(sessionId: "live", model: "model-a", effort: nil)
precondition(automatic["reasoningEffort"] is NSNull)
do { _ = try ipc().updateModelSettings(sessionId: "reject", model: "model-b", effort: "max"); preconditionFailure("ignored rejection") } catch {}
print("PASS: dynamic paginated models, supported efforts, project defaults, owner null, saved fallback, confirmed next-turn updates, rejection propagation")
'''
    (root/'main.swift').write_text('import Foundation\nimport Darwin\n'+code+fixture)
    env = dict(os.environ, DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
    try:
        subprocess.run(['xcrun','swiftc',str(root/'main.swift'),'-o',str(root/'checks')],env=env,check=True)
        subprocess.run([str(root/'checks'),str(root)],env=env,check=True,timeout=20)
        assert not errors, errors
        methods = [json.loads(line)['method'] for line in (root/'rpc-calls').read_text().splitlines()]
        assert set(methods) <= {'initialize','model/list','thread/read','config/read'}, methods
    finally:
        stopped.set(); server.close()
