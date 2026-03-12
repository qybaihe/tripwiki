# main_coordinator_rules.md

## Tripwiki 主线程协调规则

主线程不是播报员，而是协调器。

### 触发介入条件（满足任一条立即介入）
- 15 分钟无新增 commit
- `controller/mode2_state.json` 中 `running` 数量 < 5
- `/root/.openclaw/workspace/cities/*.md` 有比 `tripwiki/cities/*.md` 更新的文件未收口
- `controller/mode2_state.json` 中存在 `needs_rewrite_preview` 或 `launch_plan_only`
- 存在占位符/残缺文件未处理
- `ISSUES.md` 中仍有 P0 / P1 未补偿城市

### 介入动作顺序
1. 先收残单（同步 workspace/cities -> tripwiki/cities，commit/push）
2. 再清异常（占位符、景点<18、缺章节）
3. 再按补偿优先级补满 5 并发（优先 P0，再 P1）
4. 子任务完成后立刻收口、必要时更新 `ISSUES.md` / README / 状态文件

### 主线程收到 cron 摘要后必须做的判断
1. 本轮是否有新 commit？
2. `running` 是否变化？
3. `needs_rewrite_preview` 是否还存在？
4. 若无推进：立即读取 `controller/mode2_state.json`，按补偿模式补位/重跑/收口，而不是等待扩城 done 增长
