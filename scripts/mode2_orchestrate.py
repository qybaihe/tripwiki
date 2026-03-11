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
PROMPT_PATH = REPO_DIR / 'scripts' / 'mode2_task_prompt.txt'
WORKERS = 5

SUFFIXES = ('特别行政区', '自治州', '地区', '盟', '市')
SKIP_NAMES = {'市辖区'}
PLACEHOLDER_MARKERS = ['本文件为 cron 主控占位符', '待生成', '下一轮将补齐']
REQUIRED_SECTIONS = ['美食', '住宿', '交通', '避坑']


def sh(args: List[str], cwd: Path | None = None) -> str:
    return subprocess.check_output(args, cwd=str(cwd or REPO_DIR), text=True).strip()


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


def save_progress(progress: Dict):
    save_json(PROGRESS_PATH, progress)


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


def build_candidates(progress: Dict, limit: int = 50) -> List[Dict]:
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


def git_status() -> str:
    return sh(['git', 'status', '--porcelain'])


def commit_if_needed(message: str) -> bool:
    if not git_status():
        return False
    sh(['git', 'add', '-A'])
    sh(['git', 'commit', '-m', message])
    sh(['git', 'push'])
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
    save_progress(progress)
    return updated


def spawn_task(city: str) -> Dict:
    prompt = PROMPT_PATH.read_text(encoding='utf-8').replace('{city}', city)
    payload = {
        'runtime': 'subagent',
        'mode': 'run',
        'label': f'tripwiki-mode2-{city}',
        'cwd': str(REPO_DIR),
        'task': prompt,
        'timeoutSeconds': 1800,
        'sandbox': 'inherit'
    }
    try:
        out = sh(['openclaw', 'tools', 'call', 'sessions_spawn', json.dumps(payload, ensure_ascii=False)], cwd=REPO_DIR)
        try:
            data = json.loads(out)
        except Exception:
            data = {'raw': out}
        data['spawn_ok'] = True
        return data
    except Exception as e:
        return {
            'spawn_ok': False,
            'error': str(e),
            'payload': payload,
        }


def sync_completed_from_workspace(progress: Dict) -> List[str]:
    synced = sync_and_commit(sync_workspace_candidates(), progress)
    if synced:
        commit_if_needed(f"chore: sync generated city guides ({', '.join(synced[:5])})")
    return synced


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=WORKERS)
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_json(STATE_PATH, {'running': []})
    progress = load_progress()

    synced = sync_completed_from_workspace(progress)

    # cleanup finished running tasks if file now exists and quality ok
    running = state.get('running', [])
    still_running = []
    completed = []
    for r in running:
        city = r['city']
        p = CITY_DIR / f'{city}.md'
        if p.exists():
            ok, _ = file_quality(p)
            if ok:
                completed.append(city)
                key = r.get('key')
                if key and key in progress.get('cities', {}):
                    progress['cities'][key]['status'] = 'done'
                continue
        still_running.append(r)
    if completed:
        save_progress(progress)
        commit_if_needed(f"chore: update progress (done): {' '.join(completed[:5])}")

    candidates = build_candidates(progress)
    running_cities = {r['city'] for r in still_running}
    open_slots = max(0, args.workers - len(still_running))
    launches = [c for c in candidates if c['city'] not in running_cities][:open_slots]

    launched = []
    launch_failures = []
    now = datetime.now().isoformat(timespec='seconds')
    for c in launches:
        res = spawn_task(c['city'])
        if res.get('spawn_ok'):
            child = res.get('childSessionKey') or res.get('sessionKey') or res.get('raw', '')
            launched.append({
                'city': c['city'],
                'key': c['key'],
                'reason': c['reason'],
                'started_at': now,
                'childSessionKey': child
            })
        else:
            launch_failures.append({
                'city': c['city'],
                'key': c['key'],
                'reason': c['reason'],
                'error': res.get('error', ''),
            })

    new_running = still_running + launched
    payload = {
        'generated_at': now,
        'workers': args.workers,
        'actions': {
            'synced_from_workspace': synced,
            'completed_since_last_run': completed,
            'launched': launched,
            'launch_failures': launch_failures,
            'launch_plan_only': [c for c in launches] if launch_failures and not launched else [],
            'running_before': running,
            'running_after': new_running,
            'needs_rewrite_preview': [c for c in candidates if c['reason'] == 'rewrite'][:10]
        },
        'summary': {
            'done': sum(1 for v in progress.get('cities', {}).values() if v.get('status') == 'done'),
            'todo': sum(1 for v in progress.get('cities', {}).values() if v.get('status') != 'done'),
            'synced_count': len(synced),
            'completed_count': len(completed),
            'launch_count': len(launched),
            'launch_failure_count': len(launch_failures),
            'running_count': len(new_running),
            'open_slots': max(0, args.workers - len(new_running))
        },
        'running': new_running
    }
    save_json(STATE_PATH, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
