#!/usr/bin/env python3
"""Exercise the production CoreText split and marquee geometry without a widget host."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[2]
source = (root / 'Widget/Animation/ActivityMarqueeText.swift').read_text()
partition = source[source.index('struct ResponseTextPartition {'):source.index('\nstruct SessionUsageView:')]
marquee = (root / 'Vendor/ReusableMarquee/Sources/MarqueeText.swift').read_text()
metrics = marquee[marquee.index('struct MarqueeMetrics {'):]
allocator=source[source.index('enum ResponseSpaceAllocation {'):]
harness = r'''
let font = NSFont.systemFont(ofSize: 13)
let short = ResponseTextPartition(text: "短い返答", font: font, width: 300, lineLimit: 3)
assert(short.prefix == "短い返答" && short.overflow.isEmpty && short.prefixLines == 1)
let paragraphs = ResponseTextPartition(text: "一行目\n二行目\n三行目\n四行目", font: font, width: 300, lineLimit: 3)
assert(paragraphs.prefix == "一行目\n二行目")
assert(paragraphs.overflow == "三行目\n四行目")
let text = String(repeating: "日本語👨‍👩‍👧‍👦文章é", count: 30)
for width: CGFloat in [1, 40, 180, 300] {
    let split = ResponseTextPartition(text: text, font: font, width: width, lineLimit: 3)
    assert(split.prefix + split.overflow == text, "Characters lost or repeated at width \(width)")
    assert(!split.overflow.isEmpty && split.prefixLines == 2)
}
for width: CGFloat in [.infinity, .nan] {
    let split = ResponseTextPartition(text: text, font: font, width: width, lineLimit: 3)
    assert(split.prefix + split.overflow == text && split.height.isFinite)
}
let ordinary = ResponseTextPartition(text: text, font: font, width: 180, lineLimit: 3)
let large = ResponseTextPartition(text: text, font: .systemFont(ofSize: 26), width: 180, lineLimit: 3)
assert(large.prefix.count < ordinary.prefix.count)
let compressed = ResponseTextPartition(text: text, font: font, width: 180, height: font.lineHeight * 2 + 3, lineLimit: 8)
assert(compressed.prefixLines == 1 && compressed.height <= font.lineHeight * 2 + 5)
let singleRow = ResponseTextPartition(text: text, font: font, width: 180, lineLimit: 1)
assert(singleRow.prefix.isEmpty && singleRow.overflow == text)
let empty = ResponseTextPartition(text: "", font: font, width: 180, lineLimit: 3)
assert(empty.height == 0 && empty.prefix.isEmpty && empty.overflow.isEmpty)
let manyLines = (1...12).map { "行\($0)" }.joined(separator: "\n")
let noCap = ResponseTextPartition(text: manyLines, font: font, width: 300)
assert(noCap.prefixLines == 12 && noCap.overflow.isEmpty)
let roomy = ResponseTextPartition(text: manyLines, font: font, width: 300, height: ceil(font.lineHeight) * 7 + 3)
assert(roomy.prefixLines == 6 && roomy.overflow.hasPrefix("行7"))
let tight = ResponseTextPartition(text: manyLines, font: font, width: 300, height: ceil(font.lineHeight) * 4 + 3)
assert(tight.prefixLines == 3 && tight.overflow.hasPrefix("行4"))
let exactFit = ResponseTextPartition(text: manyLines, font: font, width: 300, height: ceil(font.lineHeight) * 12)
assert(exactFit.prefix == manyLines && exactFit.overflow.isEmpty)
assert(ResponseSpaceAllocation.heights(ideal: [20, 200], available: 100) == [20, 80])
assert(ResponseSpaceAllocation.heights(ideal: [200, 200], available: 100) == [50, 50])
assert(ResponseSpaceAllocation.heights(ideal: [20, 20], available: 100) == [20, 20])
assert(ResponseSpaceAllocation.heights(ideal: [], available: 100).isEmpty)
let metrics = MarqueeMetrics(measuredSize: CGSize(width: 40, height: 16), lineHeight: 16, spacing: 32, speed: 40)
assert(!metrics.shouldAnimate(viewportWidth: 180, isEnabled: true, reduceMotion: false))
assert(metrics.shouldAnimate(viewportWidth: 180, isEnabled: true, reduceMotion: false, scrollWhenFits: true))
assert(!metrics.shouldAnimate(viewportWidth: 180, isEnabled: true, reduceMotion: true, scrollWhenFits: true))
assert(!metrics.shouldAnimate(viewportWidth: 0, isEnabled: true, reduceMotion: false, scrollWhenFits: true))
print("PASS: exact hidden suffix, multiline/emoji boundaries, Dynamic Type, compressed heights and Reduce Motion")
'''
with tempfile.TemporaryDirectory(prefix='claudelive-overflow-') as temp:
    folder = Path(temp)
    swift = folder / 'main.swift'
    swift.write_text('import AppKit\nimport CoreText\ntypealias UIFont = NSFont\nextension NSFont { var lineHeight: CGFloat { ceil(ascender - descender + leading) } }\n' + partition + allocator + metrics + harness)
    subprocess.run(['swiftc', str(swift), '-o', str(folder / 'tests')], check=True)
    subprocess.run([str(folder / 'tests')], check=True)
