#!/usr/bin/env python3
"""Render the production widget family layouts using a static marquee on macOS."""
from pathlib import Path
import ast
import subprocess
import tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'Widget/ClaudeLiveSessionsWidget.swift').read_text()
view=source[source.index('private struct SessionsWidgetView:'):]
# WidgetKit owns this read-only environment key; inject the same value for ImageRenderer.
view=view.replace('@Environment(\\.widgetFamily) private var family', 'var family: WidgetFamily')
entry=source[source.index('struct SessionWidgetEntry:'):source.index('struct SessionsWidgetProvider:')]
store=(root/'Shared/SessionWidgetStore.swift').read_text()
models=store[store.index('struct WidgetSession:'):store.index('enum SessionWidgetStore {')]
component=(root/'Widget/Animation/ActivityMarqueeText.swift').read_text().replace('import UIKit','@preconcurrency import AppKit\ntypealias UIFont = NSFont\nextension NSFont { var lineHeight: CGFloat { ceil(ascender - descender + leading) } }')
typography=(root/'Shared/SessionTitleFont.swift').read_text().replace('#if canImport(UIKit)', '#if canImport(AppKit)').replace('import UIKit', '')
markdown=(root/'Shared/MarkdownTable.swift').read_text().split('// MARK: - 表示')[0]
style=(root/'Widget/ClaudeLiveActivityWidget.swift').read_text().split('func styledMarkdown(',1)[1].split('struct ClaudeLiveActivityWidget:',1)[0]
style='func styledMarkdown('+style
previous=ast.parse((root/'mac/tests/test_reply_layout.py').read_text())
standin=ast.literal_eval(next(n.value for n in previous.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='standin' for t in n.targets)))
icon=r'''
struct StatusIconView: View {
    let status: ClaudeStatus
    let provider: SessionProvider
    let size: CGFloat
    var animateWhenWorking: Bool = false
    var body: some View {
        Image(systemName: status.icon).font(.system(size:size)).foregroundStyle(status.color(for:provider))
            .frame(width:size,height:size)
    }
}
'''
harness=r'''
@main struct Render {
    @MainActor static func main() throws {
        let output=URL(fileURLWithPath:CommandLine.arguments[1])
        let sessions=[
            WidgetSession(id:"one",title:"Widgetの表示をサイズに合わせて改善する",project:"ClaudeLive",status:"done",
                summary:String(repeating:"返答は表示できる行を残し、収まらなかった続きだけをマーキーで表示します。",count:8),startedAt:3,provider:"codex",tokenCount:12345,weeklyUsedPercent:43),
            WidgetSession(id:"two",title:"通知配信の状態を確認する",project:"Daemon",status:"working",
                summary:"通知の配信状態を確認しています。変更した内容と次の確認事項を表示します。",startedAt:2,provider:"claude",tokenCount:2400,weeklyUsedPercent:26),
            WidgetSession(id:"three",title:"質問への回答を待っています",project:"ClaudeLive",status:"question",
                summary:"表示方法はこのまま進めてよいですか？長い質問もマーキーで確認できます。",startedAt:1,provider:"codex",tokenCount:4200,weeklyUsedPercent:43),
            WidgetSession(id:"four",title:"他の作業",project:"Tools",status:"waiting",summary:"待機中",startedAt:0,provider:"claude")
        ]
        let cases:[(String,WidgetFamily,CGFloat,CGFloat,Int,Bool)] = [
            ("small",.systemSmall,160,160,4,true),
            ("medium",.systemMedium,344,160,4,true),
            ("medium-single",.systemMedium,344,160,1,true),
            ("large",.systemLarge,344,344,4,true),
            ("large-single",.systemLarge,344,344,1,true),
            ("offline",.systemSmall,160,160,1,false),
            ("empty",.systemSmall,160,160,0,false)
        ]
        for (name,family,width,height,count,connected) in cases {
            let entry=SessionWidgetEntry(date:Date(),snapshot:SessionWidgetSnapshot(sessions:Array(sessions.prefix(count)),updatedAt:Date()),connected:connected)
            let renderer=ImageRenderer(content:SessionsWidgetView(entry:entry,family:family)
                .frame(width:width-32,height:height-32).padding(16).background(Color.black).foregroundStyle(.white).id(name))
            renderer.scale=2
            guard let image=renderer.cgImage else { fatalError("No image: "+name) }
            assert(image.width==Int(width*2) && image.height==Int(height*2))
            try NSBitmapImageRep(cgImage:image).representation(using:.png,properties:[:])!.write(to:output.appendingPathComponent(name+".png"))
            print("Rendered",name)
        }
    }
}
'''
output=Path('/tmp/claudelive-widget-family-check');output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='claudelive-widget-families-') as temp:
    folder=Path(temp);swift=folder/'Render.swift'
    swift.write_text('import WidgetKit\n'+component+typography+markdown+style+(root/'Shared/ClaudeBrandColor.swift').read_text()+(root/'Shared/ClaudeStatus.swift').read_text()+models+entry+standin+icon+view+harness)
    subprocess.run(['swiftc','-parse-as-library',str(swift),'-o',str(folder/'render')],check=True)
    subprocess.run([str(folder/'render'),str(output)],check=True)
print('Widget family layout render checks passed:',output)
