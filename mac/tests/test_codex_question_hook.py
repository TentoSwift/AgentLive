import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("question_hook", ROOT / "codex_question_hook.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class QuestionHookTests(unittest.TestCase):
    def event(self, questions, name="functions.request_user_input_async"):
        return {"hook_event_name": "PreToolUse", "tool_name": name,
                "session_id": "fixture", "tool_input": {"questions": questions}}

    def test_async_and_standard_formats(self):
        event = hook.normalize(self.event([{"title": "どう進める？", "options": ["A", "B"]}]))
        self.assertEqual(event["tool_input"]["questions"][0]["options"], [{"label": "A"}, {"label": "B"}])
        event = hook.normalize(self.event([{"question": "理由は？"}], "request_user_input"))
        self.assertEqual(event["tool_input"]["questions"][0]["options"], [])
        self.assertIsNone(hook.normalize(self.event([], "Bash")))

    def test_only_supported_answer_is_printed(self):
        event = self.event([{"title": "選択", "options": ["A"]}])
        decision = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                    "permissionDecision": "deny", "permissionDecisionReason": "ユーザーはAを選択"}}
        for response, expected in [(decision, decision), ({}, None), ({"hookSpecificOutput": {"permissionDecision": "allow"}}, None)]:
            output = io.StringIO()
            with patch.object(hook.sys, "stdin", io.StringIO(json.dumps(event))), patch.object(hook.sys, "stdout", output), patch.object(hook.urllib.request, "urlopen", return_value=io.StringIO(json.dumps(response))):
                hook.main()
            self.assertEqual(json.loads(output.getvalue()) if output.getvalue() else None, expected)

    def test_connection_failure_passes_through(self):
        with patch.object(hook.sys, "stdin", io.StringIO(json.dumps(self.event([{"title": "質問"}])))), patch.object(hook.sys, "stdout", io.StringIO()) as output, patch.object(hook.sys, "stderr", io.StringIO()), patch.object(hook.urllib.request, "urlopen", side_effect=OSError("offline")):
            hook.main()
            self.assertEqual(output.getvalue(), "")

    def test_installer_preserves_other_hooks_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hooks.json"
            other = {"matcher": "Bash", "hooks": [{"type": "command", "command": "custom-hook"}]}
            path.write_text(json.dumps({"hooks": {"PreToolUse": [other]}}))
            env = {**os.environ, "CODEX_HOME": directory}
            for _ in range(2):
                subprocess.run(["python3", str(ROOT / "install_codex_hooks.py")], env=env, check=True, capture_output=True)
            entries = json.loads(path.read_text())["hooks"]["PreToolUse"]
            self.assertIn(other, entries)
            question_entries = [e for e in entries if any("codex_question_hook.py" in h["command"] for h in e["hooks"])]
            self.assertEqual(len(question_entries), 1)
            self.assertEqual(question_entries[0]["hooks"][0]["timeout"], 600)


if __name__ == "__main__":
    unittest.main()
