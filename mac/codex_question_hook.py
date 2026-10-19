#!/usr/bin/env python3
"""Hold a supported Codex question hook and return the user's answer as context."""
import json
import sys
import urllib.request


def normalize(event):
    name = event.get("tool_name", "").replace("/", ".").split(".")[-1]
    if event.get("hook_event_name") != "PreToolUse" or name not in (
        "request_user_input", "request_user_input_async"
    ):
        return None
    tool_input = event.get("tool_input", {})
    if isinstance(tool_input, str):
        tool_input = json.loads(tool_input)
    questions = []
    for question in tool_input.get("questions", []):
        text = question.get("question") or question.get("title")
        if not isinstance(text, str) or not text.strip():
            return None
        options = question.get("options") or []
        labels = [option if isinstance(option, str) else option.get("label")
                  for option in options]
        questions.append({"question": text, "options": [
            {"label": label} for label in labels if isinstance(label, str) and label],
            "multiSelect": False})
    if not 1 <= len(questions) <= 4:
        return None
    return {**event, "provider": "codex", "tool_input": {"questions": questions}}


def main():
    try:
        event = normalize(json.load(sys.stdin))
        if event is None:
            return
        request = urllib.request.Request(
            "http://127.0.0.1:53536/question",
            data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=590) as response:
            output = json.load(response)
        # Emit only the supported denial shape; an empty response leaves the normal UI intact.
        specific = output.get("hookSpecificOutput", {})
        if (specific.get("hookEventName") == "PreToolUse"
                and specific.get("permissionDecision") == "deny"
                and isinstance(specific.get("permissionDecisionReason"), str)):
            print(json.dumps({"hookSpecificOutput": specific}, ensure_ascii=False))
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"ClaudeLive question delivery failed: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
