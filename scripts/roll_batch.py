#!/usr/bin/env python3
# Roll next batch of cities in BACKLOG.md, create placeholder guides if missing, and commit/push.
# This runs inside an isolated cron agent context. It does NOT spawn subagents.
# It focuses on deterministic repo updates + reporting.

import os, re, subprocess, datetime

REPO_DIR = os.environ.get("REPO_DIR", "/root/.openclaw/workspace/tripwiki")
BATCH = int(os.environ.get("BATCH_SIZE", "5"))

BACKLOG = os.path.join(REPO_DIR, "BACKLOG.md")
CITIES_DIR = os.path.join(REPO_DIR, "cities")

def sh(cmd: str, check=True) -> str:
    out = subprocess.run(cmd, shell=True, cwd=REPO_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if check and out.returncode != 0:
        raise RuntimeError(f"cmd failed ({out.returncode}): {cmd}\n{out.stdout}")
    return out.stdout.strip()

def read_backlog() -> str:
    with open(BACKLOG, "r", encoding="utf-8") as f:
        return f.read()

def write_backlog(txt: str):
    with open(BACKLOG, "w", encoding="utf-8") as f:
        f.write(txt)

def next_cities(txt: str, n: int):
    cities=[]
    for m in re.finditer(r"^\- \[ \] (.+)$", txt, flags=re.M):
        cities.append(m.group(1).strip())
        if len(cities) >= n:
            break
    return cities

def mark_done(txt: str, cities):
    for c in cities:
        txt = re.sub(rf"^\- \[ \] {re.escape(c)}$", f"- [x] {c}", txt, flags=re.M)
    return txt

def ensure_placeholder(city: str):
    path = os.path.join(CITIES_DIR, f"{city}.md")
    if os.path.exists(path):
        return False
    today = datetime.date.today().isoformat()
    content = f"# {city}\n\n- 更新时间：{today}\n- 推荐指数（整体）：⭐?（待生成）\n\n> 本文件为 cron 主控占位符：已进入生成队列，下一轮将补齐景点/门票/路线等细节。\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def main():
    if not os.path.exists(BACKLOG):
        raise SystemExit("BACKLOG.md missing")

    sh("git pull --rebase", check=False)

    txt = read_backlog()
    cities = next_cities(txt, BATCH)
    if not cities:
        print("No pending cities.")
        return

    created=[]
    for c in cities:
        if ensure_placeholder(c):
            created.append(c)

    # Mark them 'in progress done' to avoid repeats. (We treat placeholder creation as progress.)
    new_txt = mark_done(txt, cities)
    write_backlog(new_txt)

    sh("git add BACKLOG.md cities/*.md", check=False)
    # commit only if staged
    diff = subprocess.run("git diff --cached --quiet", shell=True, cwd=REPO_DIR)
    if diff.returncode == 0:
        print("Nothing to commit.")
        return

    msg = "chore: roll next batch placeholders (" + ", ".join(cities) + ")"
    sh(f"git commit -m {msg!r}")
    sh("git push", check=False)

    print("Rolled cities: " + ", ".join(cities))
    if created:
        print("Created placeholders: " + ", ".join(created))

if __name__ == "__main__":
    main()
