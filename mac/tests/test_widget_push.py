#!/usr/bin/env python3
"""Check production APNs topics and backwards-compatible widget token storage."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
topic = source[source.index('    static func topic('):source.index('    private func base64URL')]
device = source[source.index('struct DeviceTokens: Codable {'):source.index('struct TokenStore: Codable {')]
harness = r'''
let bundle = "com.tento.ClaudeLive"
assert(APNSClient.topic(bundleId: bundle, pushType: "widgets") == bundle + ".push-type.widgets")
assert(APNSClient.topic(bundleId: bundle, pushType: "liveactivity") == bundle + ".push-type.liveactivity")
assert(APNSClient.topic(bundleId: bundle, pushType: "alert") == bundle)
let legacy = Data(#"{"pushToStartToken":"existing","activityTokens":{"session":"activity"}}"#.utf8)
var device = try! JSONDecoder().decode(DeviceTokens.self, from: legacy)
assert(device.widgetPushToken == nil && device.pushToStartToken == "existing")
device.widgetPushToken = "aabbcc"
let restored = try! JSONDecoder().decode(DeviceTokens.self, from: JSONEncoder().encode(device))
assert(restored.widgetPushToken == "aabbcc" && restored.activityTokens["session"] == "activity")
device.widgetPushToken = nil
let removed = try! JSONDecoder().decode(DeviceTokens.self, from: JSONEncoder().encode(device))
assert(removed.widgetPushToken == nil && removed.pushToStartToken == "existing")
print("Widget APNs topic and token compatibility tests passed")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-widget-tests-') as directory:
    root = Path(directory)
    script = root / 'main.swift'
    script.write_text('import Foundation\n' + device + 'enum APNSClient {\n' + topic + '}\n' + harness)
    subprocess.run(['swiftc', str(script), '-o', str(root / 'tests')], check=True)
    subprocess.run([str(root / 'tests')], check=True)
