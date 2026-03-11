# main_coordinator_rules.md

## Tripwiki 主线程协调规则

主线程不是播报员，而是协调器。

### 触发介入条件（满足任一条立即介入）
- 15 分钟无新增 commit
- 15 分钟 done 不增长
- `controller/mode2_state.json` 中 `running` 数量 < 5
- `/root/.openclaw/workspace/cities/*.md` 有比 `tripwiki/cities/*.md` 更新的文件未收口
- 存在占位符/残缺文件未处理

### 介入动作顺序
1. 先收残单（同步 workspace/cities -> tripwiki/cities，commit/push）
2. 再清异常（占位符、景点<18、缺章节）
3. 再补满 5 并发
4. 子任务完成后立刻收口、更新 progress、清理 running

### 主线程收到 cron 摘要后必须做的判断
1. 本轮是否有新 commit？
2. done 是否增长？
3. running 是否变化？
4. 若无推进：立即读取 `controller/mode2_state.json` 并补位/重跑/收口
