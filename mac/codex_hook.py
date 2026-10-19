#!/usr/bin/env python3
"""Forward a Codex lifecycle event to the local ClaudeLive daemon.

No stdout is emitted: Codex interprets hook stdout as control data.
"""

import json
import sys
import urllib.request


def main():
    try:
        event = json.load(sys.stdin)
        event["provider"] = "codex"
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            "http://127.0.0.1:53536/hook",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=1):
            pass
    except (OSError, ValueError) as error:
        # Monitoring must never block a Codex turn when the daemon is unavailable.
        print(f"ClaudeLive hook delivery failed: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
