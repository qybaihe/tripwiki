#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

REPO_DIR = Path('/root/.openclaw/workspace/tripwiki')
WORKSPACE_CITY_DIR = Path('/root/.openclaw/workspace/cities')
PROGRESS_PATH = REPO_DIR / 'data' / 'progress.json'
CITIES_CSV = REPO_DIR / 'data' / 'cities_all.csv'
CITY_DIR = REPO_DIR / 'cities'
STATE_DIR = REPO_DIR / 'controller'
STATE_PATH = STATE_DIR / 'mode2_state.json'
WORKERS = 5

SUFFIXES = ('特别行政区', '自治州', '地区', '盟', '市')
SKIP_NAMES = {'市辖区'}
PLACEHOLDER_MARKERS = [
    '本文件为 cron 主控占位符',
    '待生成',
    '下一轮将补齐'
]
REQUIRED_SECTIONS = ['美食', '住宿', '交通', '避坑']


def norm(name: str) -> str:
    s = name.strip()
    for suf in SUFFIXES:
        if s.endswith(suf):
            return s[:-len(suf)]
    return s


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def load_progress() -> Dict:
    return load_json(PROGRESS_PATH, {'version': 1, 'cities': {}})


def load_city_rows() -> List[Dict[str, str]]:
    with CITIES_CSV.open('r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def existing_repo_files() -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for p in CITY_DIR.glob('*.md'):
        if p.name == '_TEMPLATE.md':
            continue
        out[p.stem] = p
        out.setdefault(norm(p.stem), p)
    return out


def file_quality(path: Path) -> Tuple[bool, List[str]]:
    if not path.exists():
        return False, ['missing']
    text = path.read_text(encoding='utf-8', errors='ignore')
    issues = []
    for m in PLACEHOLDER_MARKERS:
        if m in text:
            issues.append('placeholder')
            break
    scenic_count = text.count('### 2.')
    if scenic_count < 18:
        issues.append(f'scenic_lt_18:{scenic_count}')
    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            issues.append(f'missing_section:{sec}')
    return len(issues) == 0, issues


def sync_workspace_candidates() -> List[Dict]:
    results = []
    if not WORKSPACE_CITY_DIR.exists():
        return results
    for p in sorted(WORKSPACE_CITY_DIR.glob('*.md')):
        repo_p = CITY_DIR / p.name
        if not repo_p.exists() or p.stat().st_mtime > repo_p.stat().st_mtime:
            results.append({'city': p.stem, 'workspace_file': str(p), 'repo_file': str(repo_p)})
    return results


def progress_key_map() -> Dict[str, str]:
    mp = {}
    for row in load_city_rows():
        name = row['name'].strip()
        province = row['province'].strip()
        key = f'{province}::{name}'
        mp[name] = key
        mp[norm(name)] = key
    return mp


def build_todo_candidates(progress: Dict, limit: int = 20) -> List[Dict]:
    rows = load_city_rows()
    repo = existing_repo_files()
    candidates = []
    for row in rows:
        province = row['province'].strip()
        name = row['name'].strip()
        if name in SKIP_NAMES:
            continue
        key = f'{province}::{name}'
        entry = progress.get('cities', {}).get(key, {})
        status = entry.get('status') or 'todo'
        repo_p = repo.get(name) or repo.get(norm(name))
        if repo_p:
            ok, issues = file_quality(repo_p)
            if not ok:
                candidates.append({'city': norm(name), 'province': province, 'key': key, 'reason': 'rewrite', 'issues': issues})
            continue
        if status == 'done':
            continue
        candidates.append({'city': norm(name), 'province': province, 'key': key, 'reason': 'todo', 'issues': []})
        if len(candidates) >= limit:
            break
    return candidates


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=REPO_DIR, text=True).strip()


def commit_if_needed(message: str) -> bool:
    status = git('status', '--porcelain')
    if not status:
        return False
    git('add', '-A')
    git('commit', '-m', message)
    git('push')
    return True


def sync_and_commit(syncs: List[Dict], progress: Dict) -> List[str]:
    updated = []
    keymap = progress_key_map()
    for item in syncs:
        src = Path(item['workspace_file'])
        dst = Path(item['repo_file'])
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding='utf-8', errors='ignore'), encoding='utf-8')
        city = item['city']
        updated.append(city)
        key = keymap.get(city)
        if key and key in progress.get('cities', {}):
            progress['cities'][key]['status'] = 'done'
    save_json(PROGRESS_PATH, progress)
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=WORKERS)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    progress = load_progress()

    syncs = sync_workspace_candidates()
    synced = sync_and_commit(syncs, progress) if syncs else []
    sync_commit = False
    if synced:
        sync_commit = commit_if_needed(f"chore: sync generated city guides ({', '.join(synced[:5])})")

    repo = existing_repo_files()
    rewrites = []
    for city, path in repo.items():
        if city != norm(city):
            continue
        ok, issues = file_quality(path)
        if not ok:
            rewrites.append({'city': city, 'file': str(path), 'issues': issues})

    state = load_json(STATE_PATH, {})
    running = state.get('running', [])
    running_cities = {x.get('city') for x in running}
    open_slots = max(0, args.workers - len(running))

    todo_candidates = [c for c in build_todo_candidates(progress, limit=args.limit) if c['city'] not in running_cities]
    launches = todo_candidates[:open_slots]

    payload = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'workers': args.workers,
        'actions': {
            'synced_from_workspace': synced,
            'sync_commit_created': sync_commit,
            'needs_rewrite': rewrites[:20],
            'launched_candidates': launches,
            'running_before': running,
        },
        'summary': {
            'done': sum(1 for v in progress.get('cities', {}).values() if v.get('status') == 'done'),
            'todo': sum(1 for v in progress.get('cities', {}).values() if v.get('status') != 'done'),
            'synced_count': len(synced),
            'rewrite_count': len(rewrites),
            'launch_count': len(launches),
            'open_slots': open_slots,
        }
    }

    new_running = running.copy()
    for c in launches:
        new_running.append({'city': c['city'], 'key': c['key'], 'started_at': payload['generated_at'], 'reason': c['reason']})
    payload['running_after'] = new_running[:args.workers]
    save_json(STATE_PATH, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
