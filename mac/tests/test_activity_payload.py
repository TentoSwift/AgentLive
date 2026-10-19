#!/usr/bin/env python3
"""Exercise production APNs byte budgeting on real multibyte replies."""
from pathlib import Path
import subprocess
import tempfile
code = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
code = code[code.index('extension APNSClient {'):code.index('// MARK: - トークン保存')]
harness = r'''
func encode(_ payload: [String: Any]) -> Data { try! JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]) }
let original = String(repeating: "完了しました👨‍👩‍👧‍👦", count: 2000)
let state: [String: Any] = ["status":"done", "lastResponse":original,
    "lastPrompt":String(repeating: "依頼", count: 150), "recentLogs":[String(repeating:"log",count:200)],
    "tokenCount":123456, "weeklyUsedPercent":43.0, "workStartedAt":100, "workEndedAt":200]
let payload: [String: Any] = ["aps":["event":"update", "content-state":state,
    "alert":["title":"完了", "body":original]]]
let bounded = APNSClient.boundedActivityPayload(payload)
assert(encode(bounded).count <= 4096)
let result = (bounded["aps"] as! [String: Any])["content-state"] as! [String: Any]
let reply = result["lastResponse"] as! String
assert(reply.hasSuffix("…") && original.hasPrefix(String(reply.dropLast())))
assert(reply.count > 300 && result["tokenCount"] as? Int == 123456)
assert(result["weeklyUsedPercent"] as? Double == 43)
assert((payload["aps"] as! [String: Any])["content-state"] as! [String:Any] as NSDictionary == state as NSDictionary)
let small: [String: Any] = ["aps":["content-state":["lastResponse":"短い返答", "status":"done"]]]
assert(encode(APNSClient.boundedActivityPayload(small)) == encode(small))
for event in ["start", "update", "end"] {
    var aps = payload["aps"] as! [String: Any]; aps["event"] = event
    aps["attributes"] = ["sessionId":"test", "projectName":"project", "hostName":"Mac"]
    let result = APNSClient.boundedActivityPayload(["aps":aps])
    assert(encode(result).count <= 4096)
}
print("PASS: APNs 4 KiB envelope, Japanese/emoji boundaries, preserved usage and unmodified full source")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-payload-') as directory:
    folder=Path(directory)
    source=folder/'main.swift'
    source.write_text('import Foundation\nenum APNSClient {}\n'+code+harness)
    subprocess.run(['swiftc',str(source),'-o',str(folder/'tests')],check=True)
    subprocess.run([str(folder/'tests')],check=True)
