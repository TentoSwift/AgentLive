"""Check startup, duplicate requests and resume using an isolated fake CLI."""
from pathlib import Path
import tempfile, subprocess, os
source=(Path(__file__).resolve().parents[1]/'ClaudeLiveDaemon.swift').read_text()
code=source[source.index('final class NotchNewCodexRunner'):source.index('// MARK: - デーモン本体')]
with tempfile.TemporaryDirectory() as d:
 root=Path(d)
 fake=root/'codex'
 fake.write_text('''#!/usr/bin/python3
import sys,json,pathlib,time
p=pathlib.Path(__file__).parent
with (p/'calls').open('a') as f:f.write(json.dumps(sys.argv[1:])+'\\n')
text=sys.stdin.read()
(p/'prompt').write_text(text)
print(json.dumps({'type':'thread.started','thread_id':'11111111-1111-4111-8111-111111111111'}),flush=True)
time.sleep(.2)
''');fake.chmod(0o700)
 fixture=r'''
let root=URL(fileURLWithPath:CommandLine.arguments[1])
let runner=NotchNewCodexRunner(executable:root.appendingPathComponent("codex").path, storage:root.appendingPathComponent("registry.json"))
let done=DispatchSemaphore(value:0)
for _ in 0..<2 {
 runner.start(text:"日本語の依頼\n2行目",cwd:root.path,requestID:"request-1",images:[root.appendingPathComponent("日本語画像.png").path],model:"test-model",reasoningEffort:"high") { id in
  precondition(id=="11111111-1111-4111-8111-111111111111");done.signal()
 }
}
for _ in 0..<2 { precondition(done.wait(timeout:.now()+5)==.success) }
precondition(runner.owns("11111111-1111-4111-8111-111111111111"))
let calls=try String(contentsOf:root.appendingPathComponent("calls"),encoding:.utf8)
precondition(calls.split(separator:"\n").count==1)
precondition(!calls.contains("日本語") && !calls.contains("dangerously"))
let arguments = try JSONDecoder().decode([String].self, from: Data(calls.split(separator:"\n")[0].utf8))
precondition(arguments == ["exec", "--json", "--skip-git-repo-check", "--model", "test-model", "-c", "model_reasoning_effort=\"high\"", "--image", root.appendingPathComponent("日本語画像.png").path, "-"])
let prompt=try String(contentsOf:root.appendingPathComponent("prompt"),encoding:.utf8)
precondition(prompt=="日本語の依頼\n2行目")
print("PASS: local session startup, duplicate request deduplication, stdin prompt, model/effort/image arguments, permissions unchanged")
'''.replace(')==.success', ') == .success')
 (root/'main.swift').write_text('import Foundation\nimport Darwin\n'+code+fixture)
 env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
 subprocess.run(['xcrun','swiftc',str(root/'main.swift'),'-o',str(root/'test')],env=env,check=True)
 subprocess.run([str(root/'test'),str(root)],check=True)
