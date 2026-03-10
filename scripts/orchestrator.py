#!/usr/bin/env python3
"""Tripwiki orchestrator (mode 2): keep N threads working on full guides.

Design goals:
- Deterministic queue in repo (`data/cities_all.csv`) + progress state (`data/progress.json`).
- Spawn up to `WORKERS` subagents from the main session to produce full guides.
- Cron should NOT spawn subagents directly; it triggers the main session to run this orchestrator.

NOTE: This file is a scaffold; main session will run it and manage subagent spawning.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

REPO_DIR = Path(os.environ.get("REPO_DIR", "/root/.openclaw/workspace/tripwiki"))
DATA_DIR = REPO_DIR / "data"
PROGRESS_PATH = DATA_DIR / "progress.json"
CITIES_CSV = DATA_DIR / "cities_all.csv"
WORKERS = int(os.environ.get("WORKERS", "5"))

@dataclass
class City:
    province: str
    name: str
    type: str

def ensure_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PROGRESS_PATH.exists():
        PROGRESS_PATH.write_text(json.dumps({"version": 1, "cities": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    ensure_files()
    print(f"WORKERS={WORKERS}")
    print(f"progress={PROGRESS_PATH}")
    print(f"cities_csv={CITIES_CSV}")
    print("This orchestrator is a scaffold; run from main session to spawn subagents.")
