#!/usr/bin/env python3
"""Render the production StandBy view at landscape/short heights with long data."""
from pathlib import Path
import ast
import re
import subprocess
import tempfile
import shutil
root=Path(__file__).resolve().parents[2]
source=(root/'Widget/ClaudeLiveActivityWidget.swift').read_text()
view=source[source.index('struct StandBySizing {'):source.index('/// watchOS の Smart Stack')]
# Replace only intent execution: the button labels and layouts remain production code.
view=re.sub(r'Button\(intent: OpenSessionIntent\(sessionId: context.attributes.sessionId\)\)', 'Button(action: {})', view)
view=re.sub(r'Button\(intent: AnswerQuestionIntent\(\s*sessionId: context.attributes.sessionId, answer: options\[index\]\)\)', 'Button(action: {})', view)
timer=source[source.index('struct ElapsedTimerText:'):]
component=(root/'Widget/Animation/ActivityMarqueeText.swift').read_text().replace('import UIKit','@preconcurrency import AppKit\ntypealias UIFont = NSFont\nextension NSFont { var lineHeight: CGFloat { ceil(ascender - descender + leading) } }')
typography=(root/'Shared/SessionTitleFont.swift').read_text().replace('#if canImport(UIKit)', '#if canImport(AppKit)').replace('import UIKit', '')
markdown=(root/'Shared/MarkdownTable.swift').read_text().split('// MARK: - 表示')[0]
style='func styledMarkdown('+source.split('func styledMarkdown(',1)[1].split('struct ClaudeLiveActivityWidget:',1)[0]
previous=ast.parse((root/'mac/tests/test_reply_layout.py').read_text())
standin=ast.literal_eval(next(n.value for n in previous.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='standin' for t in n.targets)))
stubs=r'''
struct ClaudeActivityAttributes {}
struct MockState {
    var sessionName="改善したセッション名を状態の隣に表示する長いタイトル"
    var sessionTitle="古いタイトル"
    var sessionProvider: SessionProvider = .codex
    var question=""
    var questionCount: Int? = 1
    var options=["このまま進める", "文字を大きく", "余白を増やす", "レイアウトを変える"]
    var lastPrompt="返信や入力も流れない"
    var lastResponse=String(repeating:"本文は表示できるだけ残し、収まらない続きだけをマーキーで表示します。", count:20)
    var detail=""
    var currentTool=""
    var startedAt=Date(timeIntervalSinceReferenceDate:100)
    var workStartedAt: Date? = Date(timeIntervalSinceReferenceDate:100)
    var workEndedAt: Date? = Date(timeIntervalSinceReferenceDate:742)
    var tokenCount: Int? = 12345
    var weeklyUsedPercent: Double? = 43
}
struct MockAttributes { var projectName="Codex · ClaudeLive"; var sessionId="test" }
struct ActivityViewContext<Attributes> {
    var state=MockState()
    var attributes=MockAttributes()
    var isStale=false
}
struct StatusIconView: View {
    let status: ClaudeStatus; let provider: SessionProvider; let size: CGFloat
    var animateWhenWorking=true
    var body: some View { Image(systemName:status.icon).font(.system(size:size)).foregroundStyle(status.color(for:provider)).frame(width:size,height:size) }
}
struct PromptIcon: View {
    let size: CGFloat; let color: Color
    var body: some View { Image(systemName:"person.crop.square").font(.system(size:size)).foregroundStyle(color).frame(width:size,height:size) }
}
struct ReplyIcon: View {
    let size: CGFloat; let color: Color; let status: ClaudeStatus; let changeTrigger: String; let provider: SessionProvider
    var body: some View { Image(systemName:"bubble.left.fill").font(.system(size:size)).foregroundStyle(color).frame(width:size,height:size) }
}
'''
harness=r'''
@main struct Render {
    @MainActor static func main() throws {
        let output=URL(fileURLWithPath:CommandLine.arguments[1])
        #if DEBUG
        assert(SessionTitleFont.uiFont(ofSize:28).fontName == "MacintoshSkeletalFilled-Regular")
        print("Debug name font registered")
        #else
        assert(SessionTitleFont.uiFont(ofSize:28).fontName != "MacintoshSkeletalFilled-Regular")
        #endif
        // StandBy asks for an ideal height before giving the activity a canvas.
        // A fixed outer frame hid this host measurement in the original tests.
        let intrinsic = ImageRenderer(content:StandByView(
            context:ActivityViewContext<ClaudeActivityAttributes>(),status:.done)
            .frame(width:568).background(Color.black).foregroundStyle(.white))
        intrinsic.scale=2
        guard let intrinsicImage=intrinsic.cgImage else { fatalError("Missing intrinsic render") }
        print("Intrinsic StandBy height:",Double(intrinsicImage.height)/2)
        assert(intrinsicImage.height >= 360,"StandBy collapsed during ideal-height measurement")
        assert(intrinsicImage.height <= 560,"StandBy exceeded its preferred canvas")
        try NSBitmapImageRep(cgImage:intrinsicImage).representation(using:.png,properties:[:])!.write(to:output.appendingPathComponent("intrinsic.png"))
        for size in [CGSize(width:852,height:392),CGSize(width:568,height:240),CGSize(width:480,height:200)] {
            let sizing=StandBySizing(size:size,safeArea:EdgeInsets(top:0,leading:0,bottom:34,trailing:0))
            assert(sizing.contentSize.height+sizing.insets.top+sizing.insets.bottom == size.height)
            assert(sizing.insets.bottom>=42)
            assert(sizing.contentSize.width+sizing.insets.leading+sizing.insets.trailing==size.width)
        }
        for (name,size,status) in [
            ("done",CGSize(width:852,height:392),ClaudeStatus.done),
            ("latin",CGSize(width:568,height:240),ClaudeStatus.done),
            ("compact",CGSize(width:568,height:240),ClaudeStatus.done),
            ("short-working",CGSize(width:480,height:200),ClaudeStatus.working),
            ("question",CGSize(width:568,height:240),ClaudeStatus.question),
            ("question-short",CGSize(width:480,height:200),ClaudeStatus.question)
        ] {
            var context=ActivityViewContext<ClaudeActivityAttributes>()
            if name == "latin" { context.state.sessionName="Codex Hello · ClaudeLive" }
            if status == .question { context.state.question="スタンバイの画面でも選択肢を切らずに表示できますか？" }
            let renderer=ImageRenderer(content:StandByView(context:context,status:status)
                .frame(width:size.width,height:size.height).background(Color.black).foregroundStyle(.white)
                .overlay(alignment:.bottom) { Capsule().fill(Color.gray).frame(width:134,height:5).padding(.bottom,6) }.id(name))
            renderer.scale=2
            guard let image=renderer.cgImage else { fatalError("Missing render") }
            try NSBitmapImageRep(cgImage:image).representation(using:.png,properties:[:])!.write(to:output.appendingPathComponent(name+".png"))
            print("Rendered",name)
        }
    }
}
'''
output=Path('/tmp/claudelive-standby-fit-check');output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='claudelive-standby-tests-') as temp:
    folder=Path(temp);swift=folder/'Render.swift'
    swift.write_text(component+typography+markdown+style+(root/'Shared/ClaudeBrandColor.swift').read_text()+(root/'Shared/ClaudeStatus.swift').read_text()+standin+stubs+view+timer+harness)
    shutil.copy2(root/'Vendor/MacintoshSkeletalFilled/MacintoshSkeletalFilled.otf', folder/'MacintoshSkeletalFilled.otf')
    subprocess.run(['swiftc','-DDEBUG','-parse-as-library',str(swift),'-o',str(folder/'render')],check=True)
    subprocess.run([str(folder/'render'),str(output)],check=True)
print('StandBy sizing/render checks passed:',output)
