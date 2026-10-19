#!/usr/bin/env python3
"""Add ClaudeLive forwarding hooks to Codex's user-level hooks.json."""

import json
import os
import shlex
import shutil
from pathlib import Path


EVENTS = (
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PermissionRequest", "PreCompact", "PostCompact", "Stop",
    "Interrupt", "SessionEnd",
)


def main():
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    settings_path = codex_home / "hooks.json"
    bridge = Path(__file__).with_name("codex_hook.py").resolve()
    command = "/usr/bin/python3 " + shlex.quote(str(bridge))
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    hooks = settings.setdefault("hooks", {})
    changed = False
    for event in EVENTS:
        entries = hooks.setdefault(event, [])
        if any("codex_hook.py" in handler.get("command", "")
               for entry in entries for handler in entry.get("hooks", [])):
            continue
        entries.append({"hooks": [{"type": "command", "command": command,
                                     "timeout": 3}]})
        changed = True
    question_command = "/usr/bin/python3 " + shlex.quote(
        str(Path(__file__).with_name("codex_question_hook.py").resolve()))
    question_entry = {
        "matcher": r"(^|[./])request_user_input(_async)?$",
        "hooks": [{"type": "command", "command": question_command, "timeout": 600}],
    }
    entries = hooks.setdefault("PreToolUse", [])
    for index, entry in enumerate(entries):
        if any("codex_question_hook.py" in handler.get("command", "")
               for handler in entry.get("hooks", [])):
            if entry != question_entry:
                entries[index] = question_entry
                changed = True
            break
    else:
        entries.append(question_entry)
        changed = True
    if changed:
        codex_home.mkdir(parents=True, exist_ok=True)
        if settings_path.exists():
            shutil.copy2(settings_path, settings_path.with_suffix(".json.claudelive.bak"))
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    print("Codex hooks を追加しました" if changed else "Codex hooks は登録済みです")


if __name__ == "__main__":
    main()
