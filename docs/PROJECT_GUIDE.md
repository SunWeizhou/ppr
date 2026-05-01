# PROJECT_GUIDE.md — StatDesk 项目交付与开发指南

> 给接手 StatDesk 的 agent 读。介绍产品是什么、最爱 UI 在哪、推荐系统怎么换。
> 工作范式见 [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md)。
> **两份必须都读完才能开始动手。**

---

## 0. 产品一句话

> StatDesk 是一个 **local-first 个人 arXiv 论文 triage 桌面**：
> 每天拉一批新论文 → 排序 → 帮一个研究员决定哪些值得读 → 进 reading 流程。
> 三个 surface：**Today（今日待分拣）/ Reading（阅读流程）/ Watch（订阅追踪）**。

不是：通用搜索引擎、团队产品、推荐云服务、知识管理工具。

---

## 1. 最爱 UI 是冻结的（核心约束）

### 1.1 它在哪里

| 维度 | 位置 |
|---|---|
| **源码 commit** | `7ead51c` "ui: restore old topbar layout (no sidenav)" |
| **Git tag** | `ui-v1.0` （本地 + 远端 origin 都有）|
| **像素截图** | `tests/visual/_anchors/today-dark-2026-04-29.png` (1440×900 dark) |
| **历史"坏样本"** | `tests/visual/_anchors/today-mobile-375-broken.png`（**不是 golden**，是已知 bug 留证）|
| **当前 main 包含它？** | ✅ 是。`git merge-base --is-ancestor ui-v1.0^{} main` → true |

**最坏情况下完整恢复**：
```bash
git checkout ui-v1.0
```

### 1.2 它的视觉特征（agent 验证 UI 是否回归用）

- Top bar：`StatDesk` wordmark + `Today / Reading / Watch` 三 nav + 右侧 `EN/中 / 暗色 / ⌘K / ⚙`
- 没有 sidenav
- Today 页：`DAILY TRIAGE` kicker + 大 serif 日期 + 11 天日期 strip（今天为中心）+ `Regenerate` 按钮
- 论文卡：category chips + serif 标题 + muted 作者 + 摘要 + italic Why-line + 5 个 ghost actions（**Relevant / Skim Later / Deep Read / Ignore / Detail**）
- 暗色模式：warm dark `#1F1E1B` 背景，不是 invert
- 无中英混排（aria-label / 命令面板 全中文）

### 1.3 怎么样不会丢（4 重保险）

1. **源码层**：tag `ui-v1.0` 永远指向 `7ead51c`
2. **像素层**：anchor PNG 提交在 git tree
3. **回归层**：`tests/visual/` Playwright + golden 像素比对（**等待首次 seed**）
4. **流程层**：`AGENT_WORKFLOW.md` §4.1 禁止 agent 动 UI 文件

⚠️ **当前 `tests/visual/golden/` 是空的**——必须 user 在自己机器上跑一次 `tests/visual/regenerate_goldens.py` 才能激活第 3 层保险。在 seed 之前，**任何动 UI 文件的 PR 都没有 CI 拦截**——agent 自觉遵守 §4.1 是当前唯一防线。

---

## 2. 项目目录布局

```
arxiv_recommender/
├── README.md                  ← 一页产品介绍
├── CHANGELOG.md               ← Keep a Changelog 格式
├── LICENSE                    ← MIT
├── pyproject.toml / setup.py  ← 包定义
├── requirements.txt           ← 运行时依赖
├── requirements-test.txt      ← 测试依赖（playwright 等）
├── constraints.txt            ← 版本上下界
│
├── app/                       ← 核心代码
│   ├── routes/                ← Flask 蓝图（页面 + API）
│   ├── viewmodels/            ← 数据 → 模板 context 适配
│   ├── services/              ← 业务逻辑（含推荐系统）
│   ├── repositories/          ← SQLite 读写
│   ├── models/                ← 数据类
│   └── data/
├── templates/                 ← Jinja2 模板（**UI 神圣不可动**）
├── static/                    ← CSS + JS（**UI 神圣不可动**）
│   ├── css/  (tokens / layout / components / pages / motion / typography)
│   └── js/   (core / inbox / modals / paper_actions / command_palette ...)
│
├── tests/
│   ├── test_*.py              ← unit / integration tests (~226 个)
│   └── visual/                ← Playwright 视觉回归（最爱 UI 护栏）
│       ├── _anchors/          ← 历史截图，包括最爱 UI baseline
│       ├── golden/            ← ✋ 等首次 seed
│       ├── fixtures/
│       ├── conftest.py
│       ├── _surfaces.py       ← 测试覆盖的 5 个页面
│       ├── test_ui_anchor.py
│       └── regenerate_goldens.py
│
├── evaluation/                ← 离线评估脚本
├── scripts/                   ← 一次性工具
├── installer/                 ← 安装相关
├── docs/
│   ├── PROJECT_GUIDE.md       ← 本文
│   ├── AGENT_WORKFLOW.md      ← 工作范式
│   ├── PRD.md                 ← 产品规范（85 行）
│   ├── ARCHITECTURE.md        ← 架构详图
│   ├── DEPLOYMENT.md          ← 部署
│   ├── AGENTS.md              ← 历史 agent 规则（应被本文 + WORKFLOW 替代）
│   ├── archive/               ← 已归档历史文档
│   └── history/2026-04/       ← 旧 PRD 归档
│
├── .github/workflows/
│   ├── tests.yml              ← unittest + lint + typecheck + security + audit
│   └── visual.yml             ← UI 改动触发 visual regression
│
├── web_server.py              ← Flask 应用入口（顶层）
├── state_store.py             ← SQLite 数据访问层（顶层）
├── config_manager.py          ← 用户配置
├── app_paths.py               ← 路径常量
├── logger_config.py           ← logging 配置
├── arxiv_recommender_v5.py    ← legacy 兼容 re-export hub（30+ 引用，不能删）
└── utils.py
```

**顶层 Python 模块**（`web_server.py / state_store.py / config_manager.py / app_paths.py / logger_config.py / arxiv_recommender_v5.py / utils.py`）将来可以挪到 `app/`，但当前**不挪**——会破坏 `setup.py` 入口 + 30+ 处导入。

---

## 3. 三个 Surface（UI 主线）

| Surface | URL | 模板 | 一句话 |
|---|---|---|---|
| **Today** | `/` | `templates/home_research.html` | 今日待分拣 |
| **Reading** | `/reading` | `templates/library_research.html`（旧名）| 已进入阅读流程 |
| **Watch** | `/watch` | `templates/monitor_research.html`（旧名）| 订阅追踪 |
| Detail | `/papers/<id>` | `templates/paper_detail.html` | 单篇论文 |
| Settings | `/settings` | `templates/settings_research.html` | 偏好设置 |
| Onboarding | `/onboarding` | `templates/onboarding.html` | 首次使用 |

> **历史命名注意**：模板还是 `_research` 后缀的旧名，**不要重命名**。这是 ui-v1.0 baseline 的一部分。如果未来 user 同意改名，需要单独提案 + 改 routes + 改 visual goldens 一并提交。

---

## 4. 推荐系统现状（**这是未来工作的主战场**）

### 4.1 同时存在两套实现

| | v1（旧）| v2（新 3 阶段）|
|---|---|---|
| 入口 | `app/services/scoring_service.py` `EnhancedScorer` | `app/services/{recall,ranker,learner,blend}.py` |
| 阶段数 | 7 个（拉取 / Zotero / 反馈 / 8 维评分 / Top N / 输出 / 缓存）| 3 个（Recall / Rank / Learn）|
| 评分 | 8 维 × 4 类组合（×权重 / +加性 / -惩罚）| 单一 [0,1] match score |
| Embedding | semantic_similarity.py | embedding_service.py |
| Feedback | feedback_learning_service.py | learner.py + logistic regression |
| 切换方式 | 默认 | `STATDESK_RANKER=v2` env flag |

### 4.2 切换通路

`app/services/daily_pipeline.py:223` 处有 feature flag 检查：

```python
# Feature flag: STATDESK_RANKER=v2 (default v1).
if os.getenv("STATDESK_RANKER") == "v2":
    # 走 recall.py → ranker.py → learner.py
else:
    # 走 scoring_service.py 旧路径
```

**未来加新引擎（如 LLM-driven, agent-driven）的 contract**：

1. 在 `app/services/` 新建 `<name>_recall.py` / `<name>_ranker.py`
2. 实现统一接口（输入：候选论文 + UserContext；输出：[(paper, score, reason)]）
3. 在 `daily_pipeline.py` 加 `elif os.getenv("STATDESK_RANKER") == "v3":`
4. **不动 v1 / v2 的代码**——共存
5. 加 `tests/test_<name>_ranker.py` 覆盖关键路径
6. 在 `evaluation/` 加 A/B 评估，跑 1 周对比 v2 看 NDCG / ignored_rate

**严禁**改 `app/viewmodels/`、`app/routes/`、`templates/`、`static/`——前端字段 contract 必须保持。

### 4.3 推荐系统的输入

| 输入 | 哪里来 |
|---|---|
| arXiv 候选 | `arxiv_source.py` MultiSourceFetcher |
| 用户关键词 | `state_store.py` keywords 表 / user_profile.json |
| Zotero 库 | `zotero_service.py` |
| 历史反馈 | `state_store.list_feedback_events()` |
| 订阅 | `subscription_service.py` |

### 4.4 推荐系统的输出（不能动的契约）

`app/viewmodels/inbox_viewmodel.py` 期望的字段：

```python
[{
    "id": str,                # canonical arXiv id
    "title": str,
    "authors": list[str],
    "abstract": str,
    "score": float,           # any range（v1 是 0~15，v2 是 0~1）
    "relevance": str,         # 一句话 why
    "categories": list[str],  # arXiv 分类
    "published_at": str,      # ISO date
    ...
}]
```

任何新引擎必须输出**这一份字段**——viewmodel 已经在适配 v1/v2 差异，新引擎遵守同样适配规则即可。

---

## 5. 测试与 CI 护栏

### 5.1 单测
```bash
python -m pytest tests/                # 226 个测试
```

### 5.2 视觉回归（**最爱 UI 护栏**）
```bash
# 仅当 tests/visual/golden/ 已 seed 时有效
python -m pytest tests/visual/         # 5 个 surface goldens
```

**首次 seed**（user 自己机器上跑一次）：
```bash
git checkout ui-v1.0
python tests/visual/regenerate_goldens.py
git checkout main
git add tests/visual/golden/
git commit -m "test(visual): seed goldens from ui-v1.0 baseline"
git push origin main
```

### 5.3 GitHub Actions
| Workflow | Trigger | 必须绿？ |
|---|---|---|
| `tests.yml` (unittest / lint / security) | 每个 push / PR | **是**（continue-on-error 的 typecheck / audit 除外） |
| `tests.yml` typecheck / audit | 同上 | continue-on-error，红了不阻塞 |
| `visual.yml` | PR 改 templates / static / viewmodels / routes / tests/visual | **是**（goldens seed 之后） |

### 5.4 当前红的项（已知 tech debt，等 PR #6/#7/#8 合）
- `unittest` install 失败（requirements 上下界不一致）→ PR #6
- `lint` 396 ruff 错（积压）→ PR #7
- `security` 13 bandit 警告 → PR #8

---

## 6. 已知 tech debt（按优先级）

| | 项 | 严重度 |
|---|---|---|
| 1 | `tests/visual/golden/` 未 seed → 视觉护栏未激活 | **高** |
| 2 | CI 长期红（PR #6/#7/#8 待合）| 高 |
| 3 | `index.html` 顶层遗留文件 | 低 |
| 4 | `docs/2026-04-09-*.md` 两份旧 PRD 没归档 | 低 |
| 5 | v1（旧 scoring_service）和 v2（新 3 阶段）共存 → 评估 v2 跑稳后删 v1 | 中 |
| 6 | 顶层 Python 模块（state_store.py 等）未归 app/ | 低 |
| 7 | `arxiv_recommender_v5.py` legacy re-export hub 仍被 30+ 处 import | 低（不能急删）|

---

## 7. 不要碰的清单（agent 必须遵守）

| 不要碰 | 理由 |
|---|---|
| `templates/**` | UI 冻结，碰它 = 破坏 ui-v1.0 baseline |
| `static/css/**` `static/js/**` | 同上 |
| `app/viewmodels/**` | 决定模板拿到什么字段，碰它 = 间接破坏 UI |
| `app/routes/inbox.py / library.py / monitor.py / settings.py` | 页面级 routing，决定渲染哪个模板 |
| `tests/visual/_anchors/*.png` | 历史 baseline 截图，不可改 |
| `ui-v1.0` tag | 最爱 UI 的 commit 锚 |
| `arxiv_recommender_v5.py` | legacy compat hub，删了 import 全爆 |

如果 task 必须碰其中之一，**走 `AGENT_WORKFLOW.md` §4.1 流程**：
- 确认 goldens 已 seed
- PR 附 before/after 截图
- 附"为什么必须改 + 对 ui-v1.0 的 diff"

---

## 8. "怎么切换论文推荐系统"——常见任务的 step-by-step

例：用户说"加一个 LLM-driven (agent-powered) 的推荐引擎"。

```
1. Researcher: survey app/services/{recall,ranker,learner,blend}.py 的接口
   → finding.md

2. Planner: 写 plan
   docs/plans/2026-XX-XX-llm-ranker.md
   - 子任务 1: app/services/llm_ranker.py 新建（实现 contract）
   - 子任务 2: daily_pipeline.py 加 STATDESK_RANKER=v3 分支
   - 子任务 3: tests/test_llm_ranker.py 单测
   - 子任务 4: evaluation/llm_ranker_eval.py 跑 A/B
   - 不动: viewmodels / routes / templates / static
   → 给 user 看，等 go

3. Implementer: 一个子任务一个 PR
   PR-A: feat(ranker): add llm_ranker.py service stub
   PR-B: feat(pipeline): wire STATDESK_RANKER=v3 to llm_ranker
   PR-C: test(ranker): unit tests for llm_ranker
   PR-D: eval: add A/B harness for v2 vs v3

4. Verifier:
   - pytest 全绿
   - 设 STATDESK_RANKER=v3 跑 daily_pipeline 一次，看 logs
   - 截图 Today 页（应该跟 ui-v1.0 baseline 完全一样——后端切换不影响 UI）

5. Lead: 汇报 user
   - 4 个 PR open
   - 跑了一次 v3，输出 20 篇推荐
   - UI 截图对比 ui-v1.0 baseline = 0 像素差
   - 建议: 先合 PR-A/B/C/D，run 1 周后看 evaluation 输出
```

---

## 9. 一句话给新 agent

> **StatDesk = 冻结的最爱 UI + 可插拔的推荐后端。你的所有创造性工作发生在 `app/services/` 推荐侧。前端一根毛都不许动。**
> **不确定就读 `AGENT_WORKFLOW.md`，再不确定就停下来问 user。**
