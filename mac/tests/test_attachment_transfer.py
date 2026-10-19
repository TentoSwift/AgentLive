"""Validate the app-to-daemon attachment handoff without messaging a session."""
from pathlib import Path
import os, subprocess, tempfile
s=(Path(__file__).resolve().parents[1]/'ClaudeLiveDaemon.swift').read_text()
code=s[s.index('struct NotchAttachmentStore {'):s.index('enum CodexDisplay {')]
harness=r'''
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: 2, pixelsHigh: 2,
    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
    colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
let png = bitmap.representation(using: .png, properties: [:])!
let id = UUID().uuidString
let image = try NotchAttachmentStore.save(png, id: id, name: "貼り付け画像.png", root: root)
let received = try Data(contentsOf: image)
precondition(received == png)
let input = try CodexPromptInput(text: "確認", attachments: [["path":image.path,"name":"画像","isImage":true]])
precondition(input.imagePaths == [image.resolvingSymlinksInPath().path] && input.text == "確認")
let permissions = try FileManager.default.attributesOfItem(atPath: image.path)[.posixPermissions] as! NSNumber
precondition(permissions.intValue == 0o600)
for badName in ["../escape.png", "/tmp/escape.png", "..", "", "folder\\file.png"] {
    do { _ = try NotchAttachmentStore.save(png, id: id, name: badName, root: root); fatalError("accepted unsafe name") }
    catch { }
}
do { _ = try NotchAttachmentStore.save(png, id: "invalid-id", name: "x.png", root: root); fatalError("accepted invalid ID") }
catch { }
let file = try NotchAttachmentStore.save(Data("document".utf8), id: UUID().uuidString, name: "資料.txt", root: root)
let document = try CodexPromptInput(text: "確認", attachments: [["path":file.path,"name":"資料.txt","isImage":false]])
precondition(document.imagePaths.isEmpty && document.text.contains("資料.txt"))
print("PASS: uploaded image/document readable by prompt validator, bytes preserved, private file permissions and path validation")
'''
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);(root/'main.swift').write_text('import Foundation\nimport AppKit\n'+code+harness)
    env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
    subprocess.run(['xcrun','swiftc',str(root/'main.swift'),'-o',str(root/'check')],env=env,check=True)
    subprocess.run([str(root/'check'),str(root/'uploads')],check=True)
