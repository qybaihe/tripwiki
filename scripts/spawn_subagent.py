#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"status": "error", "error": "expected one JSON payload arg"}, ensure_ascii=False))
        return 2
    payload = json.loads(sys.argv[1])
    # Placeholder bridge: this script makes the failure mode explicit and keeps
    # mode2_orchestrate.py off the broken `openclaw tools call ...` path.
    # Real spawning is still handled by the parent OpenClaw agent via sessions_spawn.
    print(json.dumps({
        "status": "bridge-unavailable",
        "error": "spawn bridge not wired to OpenClaw tool runtime yet; use parent-agent sessions_spawn fallback",
        "payload": payload,
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
