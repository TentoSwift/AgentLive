#!/usr/bin/env python3
"""Compile generated Mac question dialogs without displaying any windows."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'ClaudeLiveDaemon.swift').read_text()
helper = source[source.index('struct QuestionItem {'):source.index('// MARK: - セッション状態')]
harness = r'''
let tests: [([QuestionItem], Bool)] = [
    ([QuestionItem(question: "どちらにしますか？", options: ["案A", "案B"], multiSelect: false)], true),
    ([QuestionItem(question: "自由入力", options: [], multiSelect: false)], true),
    ([QuestionItem(question: "引用符\"と\\改行\nを含む質問", options: ["その他（自由入力）", "A\"B"], multiSelect: true),
      QuestionItem(question: "理由", options: [], multiSelect: false)], true),
    ([QuestionItem(question: "Claudeの質問", options: ["A", "B"], multiSelect: false)], false)
]
for (index, value) in tests.enumerated() {
    let script = QuestionDialogScript.make(items: value.0, title: "ClaudeLive · Test", allowCustom: value.1)
    if value.1 && !value.0[0].options.isEmpty { assert(script.contains("その他（自由入力）")) }
    if value.0[0].options.isEmpty { assert(script.contains("display dialog") && !script.contains("item 1 of opts")) }
    try! script.write(toFile: CommandLine.arguments[1] + "/dialog-\(index).applescript", atomically: true, encoding: .utf8)
}
'''
with tempfile.TemporaryDirectory(prefix='claudelive-mac-dialog-tests-') as directory:
    root = Path(directory)
    (root / 'main.swift').write_text('import Foundation\n' + helper + harness)
    subprocess.run(['swiftc', str(root / 'main.swift'), '-o', str(root / 'tests')], check=True)
    subprocess.run([str(root / 'tests'), directory], check=True)
    for script in root.glob('*.applescript'):
        subprocess.run(['osacompile', '-o', str(script.with_suffix('.scpt')), str(script)], check=True, capture_output=True)
print('Mac question dialog generation and AppleScript compilation tests passed')
