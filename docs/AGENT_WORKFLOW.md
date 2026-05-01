# AGENT_WORKFLOW.md — Multi-Agent 工作范式

> 本文件**给所有在本仓库工作的 agent 读**，定义工作流程、角色分工、硬约束。
> 项目代码理解见 [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md)。
> 任何 agent 在动手之前先读完两份。

---

## 0. 一句话原则

> **最爱 UI 是冻结的。所有未来工作只在推荐系统后端发生。任何动 UI 文件的 PR 必须被 visual regression workflow 拦截。**

---

## 1. 项目当前状态（agent 接手前必知）

| 维度 | 状态 |
|---|---|
| **最爱 UI baseline** | tag `ui-v1.0` → commit `7ead51c`，已包含在 main 之中 |
| **像素级锚点** | `tests/visual/_anchors/today-dark-2026-04-29.png`（在 git tree 里，永不丢失） |
| **Visual regression scaffold** | `tests/visual/` 已搭好，`golden/` 等待首次 seed |
| **推荐系统现状** | 同时存在 v1（旧 `scoring_service.py` 等）+ v2（新 `recall.py / ranker.py / learner.py`），通过 `STATDESK_RANKER` env flag 切换 |
| **CI 状态** | red — 3 个 fix PR (#6/#7/#8) 待合 |
| **工作树** | 偶尔脏（之前 agent 擅自动 UI 留下的痕迹） |

接手时**先**：
```bash
git status -s                              # 必须 clean，否则先 stash 或丢弃
git fetch origin --prune
git checkout main && git pull --ff-only
git log --oneline -3                       # 跟 origin 一致
git tag | grep ui-v1.0                     # 必须有
```

---

## 2. 角色（Roles）

定义 5 个 sub-agent 角色。**Lead agent** 不直接写代码，只调度。

| 角色 | 职责 | 工具范围 | 不准做 |
|---|---|---|---|
| **Lead** | 接任务 / 拆解 / 调度 sub-agent / 汇总 / 给 user 汇报 | TodoWrite + 调度子 agent | 写代码 / 直接 commit |
| **Researcher** | 探索代码、grep、读文件、survey、返回 finding | Read / Grep / Bash (read-only) | Write / Edit / git mutate |
| **Planner** | 把 Research 结果转成具体可执行的 plan doc | Write (只能写 docs/plans/*.md) | 改业务代码 |
| **Implementer** | 按 approved plan 写代码 | Read / Write / Edit / Bash / git | 超出 plan 的改动 |
| **Reviewer** | PR / commit 审 (UI parity / 测试覆盖 / scope) | Read / Grep / Bash | 写代码 |
| **Verifier** | 跑测试、跑应用、截图、报告事实 | Read / Bash / Playwright | Write / commit |

**Lead agent 调度方式**：通过 Task tool 启动 sub-agent，明确给出"角色 + 输入 + 期望输出 + 边界"。例：

```
角色：Researcher
输入：定位 daily_pipeline.py 中 STATDESK_RANKER feature flag 的所有读取点
期望输出：文件路径 + 行号 + 周边 5 行代码 + 一句解释
边界：只读不写
```

---

## 3. 标准工作流（5 阶段）

```
Receive → Research → Plan → Implement → Verify → Report
```

任何任务（即便看起来很小）都必须走这 5 步。**禁止跳步**。

### 3.1 Receive（接任务）
Lead 收到 user 任务后立即输出 3 件事：
1. **任务理解一句话**（"我理解你要……")
2. **范围澄清问题**（如有歧义，必须先问）
3. **不在范围内的事**（明确"我**不会**做 X、Y、Z"）

发给 user 等确认。**不准在 user 没确认前就开 sub-agent**。

### 3.2 Research（调研）
Lead → Researcher。Researcher 返回 Markdown 格式的 finding：
- 涉及哪些文件
- 当前实现是什么
- 已知约束 / 类似的过去工作
- 提议的入手点

**Researcher 不准提解决方案**——只报事实。

### 3.3 Plan（制定方案）
Lead 自己写或 → Planner，输出 `docs/plans/YYYY-MM-DD-<task>.md`。结构：
- 目标（一句话）
- 子任务清单（每条 ≤ 300 行 diff）
- 每条子任务：动哪些文件 / 输入 / 验收 / 风险
- 回退方案
- 不在范围内（second time，重申）

**给 user 看 plan，等明确"go"再继续**。User 可以否决/修改。

### 3.4 Implement（实现）
Lead → Implementer，每次只交一个子任务。Implementer 必须：
1. 在 feature branch 上工作（`<role>/<short-name>`，如 `feat/recall-arxiv-batched`）
2. **每个 sub-task 一个 PR**，diff ≤ 300 行（不算删除和测试）
3. PR 描述里链回 plan 文件的具体子任务编号
4. 自检：本地能跑、测试通过、未触碰非 plan 范围内文件

完成后通知 Lead，**不许自己合 PR**。

### 3.5 Verify（验证）
Lead → Verifier。Verifier 跑：
- `python -m pytest tests/` （必须绿）
- `python -m pytest tests/visual/`（如改了 UI 路径下文件，必须绿）
- 启动应用 + Playwright 跑选定 surface 截图
- 输出：✓ 跑通 / ✗ 失败 + 失败原因截图

Verifier **只报事实**，不修。

### 3.6 Report（汇报）
Lead 给 user **完整**汇报。模板：

```markdown
## 任务：<one line>

### 做了什么
- PR #X (merged): ...
- PR #Y (open, 等 visual 绿): ...

### 没做什么（明示）
- 没动 templates/、static/、viewmodels/（除非任务要求）
- Z 任务超出 scope，建议下次单独提

### 验证证据
- pytest: 226 / 226 passed
- visual: 5/5 goldens match
- 实际界面截图: <path>

### 我开的所有 PR
$(gh pr list --state open --author @me --json number,title --jq '.[] | "  #\(.number) \(.title)"')

### 下一步建议
- ...
```

**汇报必须列全 PR**——包括"顺手"开的（其实不该顺手开）。

---

## 4. 硬约束（不可突破）

### 4.1 UI 神圣
**禁止动**以下文件，除非 user 明确说"改 UI"：
- `templates/**`
- `static/css/**`、`static/js/**`
- `app/viewmodels/**`（输出给前端的字段）
- `app/routes/**`（页面级路由）

如果 task 必须动 UI：
- 必须先确认 `tests/visual/golden/` 已 seed（`ls tests/visual/golden/*.png` 至少 1 个）
- PR description 里必须附 before/after 截图
- 必须附"对 ui-v1.0 baseline 的差异说明"

### 4.2 Scope 不许扩
- 不准看到一个 bug 就顺手开 fix PR
- 发现新问题 → 写进 report 的"建议下次"段，让 user 决定
- 任何"顺手"行为视为违规，PR 会被关掉

### 4.3 PR 体量
- Diff ≤ 300 行（不含删除和测试）
- 一个 PR 一个 concern
- PR 标题：`<type>(<scope>): <imperative>`，例 `feat(ranker): add v3 hybrid scorer behind feature flag`

### 4.4 Branch 命名
- `feat/<short-name>` —— 新功能
- `fix/<short-name>` —— bugfix
- `refactor/<short-name>` —— 重构
- `docs/<short-name>` —— 纯文档
- `chore/<short-name>` —— 杂项

完成后 **`gh pr merge --squash --delete-branch`**，不留 stale branch。

### 4.5 不许自合 PR
所有 PR **等 user 说 "merge"** 才合。Lead 可以建议，但不能 `gh pr merge` 不告而合。

### 4.6 失败时停下
- 测试挂 3 次还修不好 → 停，向 user 汇报
- 发现需要改 PRD / 改架构 → 停，向 user 汇报
- 不确定 → 停，向 user 汇报

**禁止用代码"绕过"测试失败**（比如 skip / xfail / `assert True`）。

---

## 5. 子 agent 调用范式

每次启动 sub-agent，prompt 必须有 6 段：

```
1. 角色：<Researcher | Planner | Implementer | Reviewer | Verifier>
2. 上下文：（一段话，说明为什么需要做这个，PROJECT_GUIDE 哪几节相关）
3. 输入：（具体文件 / 数据 / 任务编号）
4. 期望输出：（格式规定）
5. 工具边界：（明确哪些工具能用，哪些不能）
6. 完成判定：（怎么知道"做完了"）
```

例（让 Researcher 调研 ranker 接口）：

```
1. 角色：Researcher
2. 上下文：用户想加一个新 ranker (v3)，需要知道 v2 的 ranker 接口长什么样
   见 PROJECT_GUIDE §5 推荐系统架构
3. 输入：app/services/ranker.py + 调用它的地方
4. 期望输出：Markdown 格式
   ## ranker.py 公开接口
   - 函数签名 + docstring 摘要
   ## 被谁调用
   - 文件:行 → 一句话用法说明
   ## 隐含约定（input/output 类型、副作用、异常）
5. 工具边界：Read / Grep / Bash (只读)；不许 Write / Edit / git mutate
6. 完成判定：返回 ≤ 200 行 Markdown，不含解决方案
```

---

## 6. 沟通格式（user ↔ Lead）

### Lead 给 user 的报告
- 一定用 **emoji + 表格 + 短句**，不要长段
- ✅ 已完成 / ⏳ 进行中 / ❌ 失败 / ⚠️ 风险
- 关键链接（PR / commit / 截图路径）放表格里
- 末尾 **"下一步建议"** 段最多 3 条

### Lead 收到 user 反馈
- 如果是新任务 → 走 §3 5 阶段
- 如果是修改之前的 plan → 改 plan 文件，**不直接改代码**
- 如果是"赶紧 / 直接做" → 仍要回一句"我即将做 A B C，没说错的话 30 秒内开始"，给 user 1 个反应窗口

---

## 7. 红线（违反则任务作废）

| 红线 | 后果 |
|---|---|
| 动 UI 文件但 visual workflow 未绿 / goldens 未 seed | PR 关掉 + 复盘 |
| 自合 PR 而 user 没说 "merge" | revert + 复盘 |
| 报告漏掉"自己开的 PR" | 复盘 + 重新汇报 |
| 单 PR > 500 行 diff | 拆 |
| 删 ui-v1.0 tag | 立刻恢复 + 复盘 |
| 删 `tests/visual/_anchors/*.png` | 立刻恢复 + 复盘 |
| 重命名 `templates/home_research.html` → `today.html` 等 | 拒绝执行（这是 ui-v1.0 baseline 的一部分） |

---

## 8. 工作流图（一图看懂）

```
                  ┌──────────────────┐
   user 发任务  → │ Lead: Receive    │ → 澄清问题给 user
                  └────────┬─────────┘
                           │ user 确认
                           ↓
                  ┌──────────────────┐
                  │ Lead → Researcher│ → finding.md
                  └────────┬─────────┘
                           │
                           ↓
                  ┌──────────────────┐
                  │ Lead 写 plan      │ → docs/plans/...md → 给 user 看
                  └────────┬─────────┘
                           │ user "go"
                           ↓
              ┌────────────────────────────┐
              │ Lead → Implementer (循环)   │ → PR #N (open)
              │   每次一个 sub-task         │
              └────────┬───────────────────┘
                       │
                       ↓
              ┌────────────────────────────┐
              │ Lead → Reviewer            │ → review notes
              │ Lead → Verifier            │ → test/visual evidence
              └────────┬───────────────────┘
                       │
                       ↓
              ┌────────────────────────────┐
              │ Lead → user 汇报           │ → user 决定 merge?
              └────────────────────────────┘
                       │
                       │ user "merge"
                       ↓
              ┌────────────────────────────┐
              │ Lead 真合 PR + 删 branch   │ → 下一个 sub-task 或任务结束
              └────────────────────────────┘
```

---

## 9. 一句话给所有 agent

> **不动 UI、不扩 scope、一次一个 PR、做完汇报全列、user 没说合不要合。**
> **不确定就停下来问。慢一点没关系，丢东西不行。**
