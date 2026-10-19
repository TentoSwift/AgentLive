#!/usr/bin/env python3
"""Render production reply layouts with a static marquee stand-in on macOS."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[2]
component=(root/'Widget/Animation/ActivityMarqueeText.swift').read_text().replace('import UIKit','import AppKit\ntypealias UIFont = NSFont\nextension NSFont { var lineHeight: CGFloat { ceil(ascender - descender + leading) } }')
typography=(root/'Shared/SessionTitleFont.swift').read_text().replace('#if canImport(UIKit)', '#if canImport(AppKit)').replace('import UIKit', '')
markdown=(root/'Shared/MarkdownTable.swift').read_text().split('// MARK: - 表示')[0]
style=(root/'Widget/ClaudeLiveActivityWidget.swift').read_text().split('func styledMarkdown(',1)[1].split('struct ClaudeLiveActivityWidget:',1)[0]
style='func styledMarkdown('+style
usage=(root/'Shared/ClaudeStatus.swift').read_text().split('func sessionUsageText(',1)[1]
usage='func sessionUsageText('+usage
standin=r'''
struct MarqueeText: View {
    let text: String
    let font: NSFont
    init(_ text: String, font: NSFont, isEnabled: Bool = true, repeatCount: Int? = nil, scrollWhenFits: Bool = false) { self.text=text; self.font=font }
    var body: some View {
        Text(text.replacingOccurrences(of:"\n",with:" ")).font(Font(font)).lineLimit(1)
            .frame(maxWidth:.infinity,alignment:.leading).frame(height:ceil(font.lineHeight))
            .background(Color.purple.opacity(0.2))
    }
}
'''
harness=r'''
struct Card: View {
    let response: String
    var body: some View {
        ReplyPriorityLayout(maxHeight:136,spacing:4) {
            if !response.isEmpty {
                HStack { Text("完了").font(.headline); Spacer(); Text("GPT-6.1 Sol  1:23").font(.caption) }.frame(height:26)
                HStack { Text("依頼した内容").font(.footnote); Spacer() }.frame(height:18)
                HStack(alignment:.top,spacing:6) {
                    Image(systemName:"bubble.left.fill").frame(width:26,height:26)
                    CompletedResponseView(text:response)
                }
                .layoutValue(key:ResponseContentKey.self,value:true)
            }
            SessionUsageView(tokenCount:1200,weeklyUsedPercent:43)
        }
        .padding(12).frame(width:360).background(Color.black).foregroundStyle(.white)
    }
}
struct WidgetCard: View {
    var body: some View {
        ReplyPriorityLayout(spacing:6) {
            ForEach(0..<2) { index in
                ReplyPriorityLayout(spacing:4) {
                    Text("完了   Session \(index)").font(.caption)
                    CompletedResponseView(text:String(repeating:"本文をなるべく表示し、はみ出した続きだけを流します。",count:12),basePointSize:12)
                        .layoutValue(key:ResponseContentKey.self,value:true)
                    SessionUsageView(tokenCount:1200,weeklyUsedPercent:43)
                }
                .layoutValue(key:ResponseContentKey.self,value:true)
            }
        }
        .frame(width:320,height:140,alignment:.topLeading).padding(12).background(Color.black).foregroundStyle(.white)
    }
}
struct WatchCard: View {
    var body: some View {
        ReplyPriorityLayout(maxHeight:100,spacing:3) {
            HStack { Text("完了").font(.caption2); Spacer(); Text("Session").font(.caption2) }.frame(height:22)
            CompletedResponseView(text:String(repeating:"Watchでも本文を残し、続きだけを流します。",count:12),basePointSize:11)
                .layoutValue(key:ResponseContentKey.self,value:true)
        }
        .padding(.horizontal,8).padding(.vertical,6).frame(width:180).background(Color.black).foregroundStyle(.white)
    }
}
@main struct Render {
    @MainActor static func main() throws {
        let directory=URL(fileURLWithPath:CommandLine.arguments[1])
        for (name,response) in [("short","短い返答は全文を表示します。"),("medium",String(repeating:"先頭からできるだけ多くの行を残して表示します。",count:4)),("long",String(repeating:"表示に収まらなかった行だけをマーキーにして、見えている本文は動かしません。",count:12))] {
            let renderer=ImageRenderer(content:Card(response:response).id(name))
            renderer.scale=2
            guard let image=renderer.cgImage else { fatalError("No image") }
            assert(image.height<=320,"Card exceeded the 160 pt safety limit")
            let data=NSBitmapImageRep(cgImage:image).representation(using:.png,properties:[:])!
            try data.write(to:directory.appendingPathComponent(name+".png"))
            print(name,"rendered height:",Double(image.height)/2)
        }
        let watch=ImageRenderer(content:WatchCard()); watch.scale=2
        guard let watchImage=watch.cgImage else { fatalError("No Watch image") }
        assert(watchImage.height<=224)
        try NSBitmapImageRep(cgImage:watchImage).representation(using:.png,properties:[:])!.write(to:directory.appendingPathComponent("watch.png"))
        let renderer=ImageRenderer(content:WidgetCard()); renderer.scale=2
        guard let image=renderer.cgImage else { fatalError("No widget image") }
        try NSBitmapImageRep(cgImage:image).representation(using:.png,properties:[:])!.write(to:directory.appendingPathComponent("widget.png"))
    }
}
'''
output=Path('/tmp/claudelive-reply-layout-check');output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='claudelive-layout-tests-') as temp:
    folder=Path(temp);source=folder/'Render.swift'
    source.write_text(component+typography+markdown+style+usage+standin+harness)
    subprocess.run(['swiftc','-parse-as-library',str(source),'-o',str(folder/'render')],check=True)
    subprocess.run([str(folder/'render'),str(output)],check=True)
print('Layout render checks passed:', output)
