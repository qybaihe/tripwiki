#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/tripwiki

echo "Tripwiki 定时简报"
echo

echo "- 最新提交：$(git log -1 --oneline)"
echo "- 近 5 次提交："
git log -5 --oneline | sed 's/^/  - /'

echo
if [ -f data/progress.json ]; then
  python3 - <<'PY'
import json
from collections import Counter
p=json.load(open('data/progress.json','r',encoding='utf-8'))
statuses=[v.get('status','todo') for v in p.get('cities',{}).values()]
print('- progress 统计：', dict(Counter(statuses)))
PY
else
  echo "- progress：未找到 data/progress.json"
fi

echo
# Show next 10 TODO from BACKLOG (if present)
if [ -f BACKLOG.md ]; then
  echo "- BACKLOG 待做（前 10）："
  grep -E '^\- \[ \] ' BACKLOG.md | head -n 10 | sed 's/^/  /' || true
fi
