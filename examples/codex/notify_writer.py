"""Example wrapper if you prefer notify -> HTTP instead of direct DB writes."""

from __future__ import annotations

import json
import sys
import urllib.request

API = "http://127.0.0.1:37770/ingest/codex-notify"


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    raw_payload = json.loads(sys.argv[1])
    body = {
        "payload": raw_payload,
        "project_from_cwd": True,
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        _ = resp.read()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
