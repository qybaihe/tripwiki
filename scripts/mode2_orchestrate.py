#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

REPO_DIR = Path("/root/.openclaw/workspace/tripwiki")
PROGRESS_PATH = REPO_DIR / "data" / "progress.json"
CITIES_CSV = REPO_DIR / "data" / "cities_all.csv"
CITY_DIR = REPO_DIR / "cities"
STATE_DIR = REPO_DIR / "controller"
STATE_PATH = STATE_DIR / "mode2_state.json"
WORKERS = 5

SUFFIXES = ("特别行政区", "自治州", "地区", "盟", "市")
SKIP_NAMES = {"市辖区"}


def norm(name: str) -> str:
    s = name.strip()
    for suf in SUFFIXES:
        if s.endswith(suf):
            return s[: -len(suf)]
    return s


def load_progress() -> Dict:
    if not PROGRESS_PATH.exists():
        return {"version": 1, "cities": {}}
    return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))


def load_existing_files() -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not CITY_DIR.exists():
        return out
    for p in CITY_DIR.glob("*.md"):
        if p.name == "_TEMPLATE.md":
            continue
        stem = p.stem
        out[stem] = p.name
        out.setdefault(norm(stem), p.name)
    return out


def load_city_rows() -> List[Dict[str, str]]:
    with CITIES_CSV.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def infer_status(row: Dict[str, str], progress: Dict, existing: Dict[str, str]) -> Tuple[str, str | None]:
    province = row["province"].strip()
    name = row["name"].strip()
    key = f"{province}::{name}"
    entry = progress.get("cities", {}).get(key, {})
    if name in SKIP_NAMES:
        return "skip", None
    if name in existing:
        return "done", existing[name]
    n = norm(name)
    if n in existing:
        return "done", existing[n]
    status = entry.get("status") or "todo"
    return status, entry.get("file")


def build_candidates(limit: int = 20) -> List[Dict[str, str]]:
    progress = load_progress()
    existing = load_existing_files()
    rows = load_city_rows()
    candidates = []
    for row in rows:
        status, file_hint = infer_status(row, progress, existing)
        if status in {"done", "skip", "in_progress"}:
            continue
        candidates.append({
            "province": row["province"].strip(),
            "name": row["name"].strip(),
            "type": row.get("type", "").strip(),
            "code": row.get("code", "").strip(),
            "file": file_hint or f"cities/{row['name'].strip()}.md",
        })
        if len(candidates) >= limit:
            break
    return candidates


def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()

    ensure_state_dir()
    candidates = build_candidates(limit=args.limit)
    payload = {
        "workers": args.workers,
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "candidates": candidates,
        "summary": {
            "candidate_count": len(candidates),
        },
    }
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
