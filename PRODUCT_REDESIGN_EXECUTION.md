# PRODUCT_REDESIGN_EXECUTION.md

## 1. 文档目的

本文件是 `PRD.md` 的执行层补充，用于把产品重设计方案进一步拆解为：
- 页面级线框说明（page-level wireframes）
- 模块职责
- 交互说明
- 开发任务清单
- 重构顺序建议

目标不是讨论理念，而是让开发者或 AI agent 能直接据此开始实现。

---

## 2. 执行总原则

### 2.1 重构顺序原则
必须按以下顺序推进，而不是先修局部样式：

1. 先收束信息架构
2. 再重写页面职责
3. 再替换关键交互
4. 再统一组件系统
5. 最后修对齐、间距、视觉细节

### 2.2 禁止事项
在完成以下重构前，不建议继续新增顶层功能：
- 新导航页
- 新的首页面板
- 新的“统计面板式”信息块
- 新的旧式静态 HTML 页面

### 2.3 实现目标
本阶段的目标不是“做出最终最强版本”，而是做出一个：
- 主线清楚
- 页面职责单一
- 数据流一致
- 易于继续迭代

的稳定骨架。

---

## 3. 新版导航与页面映射

## 3.1 一级导航
统一为：
- Inbox
- Queue
- Library
- Monitor
- Settings

## 3.2 当前功能向新结构迁移映射

### 当前首页 / 今日推荐
-> 新 `Inbox`

### 当前 liked / favorites / queue 混合状态
-> 新 `Queue` + `Library/Saved Papers`

### 当前 collections / saved searches / 历史
-> 新 `Library` 与 `Monitor` 分拆

### 当前 scholars / journal / track
-> 新 `Monitor`

### 当前关键词管理 / zotero / 偏好
-> 新 `Settings`

### 当前 search 页
-> 从顶层页面降为：
- Inbox 的“继续探索”抽屉或二级页
- Monitor 的 Query Subscription 创建入口
- Library 内部的 scoped search

---

## 4. 页面级线框说明

# 4.1 Inbox 页面线框

## 4.1.1 页面目标
让用户高效完成“今日论文分拣”。

## 4.1.2 页面结构

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Nav: Inbox | Queue | Library | Monitor | Settings       │
├──────────────────────────────────────────────────────────────┤
│ Page Header                                                 │
│ 标题：Inbox / 今日待分拣论文                                 │
│ 副标题：今天先判断哪些论文值得进入阅读流程                    │
│ [刷新今日结果]  [继续探索]                                   │
├──────────────┬──────────────────────────────┬───────────────┤
│ Left Rail    │ Center List                  │ Right Panel   │
│ 日期切换      │ 排序后的论文列表              │ 选中论文详情     │
│ 状态筛选      │ title / authors / tags       │ 标题 / 作者      │
│ 今日主题摘要   │ short summary / score        │ 摘要            │
│ job status    │ relevant state / queue state │ Why this       │
│              │                              │ Relevant       │
│              │                              │ Ignore         │
│              │                              │ Skim Later     │
│              │                              │ Deep Read      │
│              │                              │ Open arXiv     │
│              │                              │ More actions   │
└──────────────┴──────────────────────────────┴───────────────┘
```

## 4.1.3 左栏模块
### 保留
- 日期切换
- 过滤器：All / Untriaged / Relevant / Ignored / Queued
- 今日主题简述
- 最近 job 状态

### 移除或降级
- collection 数量
- saved search 数量
- 复杂资产摘要
- 过多的 monitor 入口

## 4.1.4 中栏列表项结构
每一项统一显示：
- rank
- title（最多 2 行）
- authors（最多 2 行）
- category tags
- short summary（最多 3 行）
- score
- queue 状态 chip
- relevant / ignored 状态边框或 chip

不在列表项中塞入过多按钮。

## 4.1.5 右栏详情结构
### 一级信息（默认展开）
- 标题
- 作者
- 摘要
- Why recommended

### 一级动作（始终可见）
- Relevant
- Ignore
- Skim Later
- Deep Read
- Open arXiv

### 二级动作（More actions）
- 加入 Collection
- 下载 PDF
- 导出 BibTeX
- 查看完整解释

## 4.1.6 首页设计约束
- 首页不直接展示所有“资产管理”动作
- 首页不承担复杂配置
- 首页主要解决“判断”和“送入流程”

---

# 4.2 Queue 页面线框

## 4.2.1 页面目标
让用户管理阅读流程，而不是重新做推荐浏览。

## 4.2.2 页面结构

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Nav                                                     │
├──────────────────────────────────────────────────────────────┤
│ Page Header: Queue / 阅读流程                               │
│ 副标题：把已经确认值得看的论文安排到合适的阅读层级             │
├──────────────────────────────────────────────────────────────┤
│ Status Tabs: Inbox | Skim Later | Deep Read | Saved | Arch. │
├──────────────────────┬───────────────────────────────────────┤
│ Queue List           │ Detail / Action Panel                 │
│ 该状态下的论文列表     │ 论文信息 / note / move status / open   │
│ 可按更新时间排序       │ add to collection / archive           │
└──────────────────────┴───────────────────────────────────────┘
```

## 4.2.3 关键功能
- 状态切换
- note 编辑
- 打开原文
- 加入 Collection
- 归档

## 4.2.4 设计要求
Queue 页面应支持真正的“推进阅读流程”，例如：
- 从 Skim Later 移到 Deep Read
- 从 Deep Read 移到 Saved
- 从任何状态归档

---

# 4.3 Library 页面线框

## 4.3.1 页面目标
沉淀长期研究资产，而不是短期分拣结果。

## 4.3.2 页面结构

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Nav                                                     │
├──────────────────────────────────────────────────────────────┤
│ Page Header: Library / 研究资产库                            │
│ 副标题：把长期有价值的论文组织成可持续使用的研究材料            │
├──────────────────────────────────────────────────────────────┤
│ Tabs: Collections | Saved Papers | History                  │
├──────────────────────┬───────────────────────────────────────┤
│ Left List / Tabs     │ Right Detail                          │
│ collection 列表       │ collection 描述 / 论文列表 / 操作       │
│ saved papers list    │ 或 paper detail                       │
│ history date list    │                                       │
└──────────────────────┴───────────────────────────────────────┘
```

## 4.3.3 Collections 子页
每个 Collection 需要支持：
- name
- description
- optional seed query
- paper count
- updated_at
- paper list

## 4.3.4 Saved Papers 子页
- 展示已保存论文
- 支持搜索和筛选
- 支持加入 Collection

## 4.3.5 History 子页
- 查看历史批次
- 回看某天推荐
- 再次送入 Queue 或 Collection

## 4.3.6 交互要求
创建 Collection 必须使用 modal/drawer，而不是 prompt。

---

# 4.4 Monitor 页面线框

## 4.4.1 页面目标
管理持续订阅对象，统一“长期追踪”能力。

## 4.4.2 页面结构

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Nav                                                     │
├──────────────────────────────────────────────────────────────┤
│ Page Header: Monitor / 长期关注                             │
│ 副标题：追踪你关心的作者、来源和研究问题                       │
├──────────────────────────────────────────────────────────────┤
│ Tabs: Authors | Venues | Queries | Recent Hits              │
├──────────────────────┬───────────────────────────────────────┤
│ Subscription List    │ Detail / Recent Hits                 │
│ 已关注对象             │ 最近命中的论文 / 说明 / 操作           │
│ 新建订阅按钮            │ add to inbox / queue / collection    │
└──────────────────────┴───────────────────────────────────────┘
```

## 4.4.3 Authors
- 已关注作者列表
- 作者简介（可选）
- 最近命中文章
- 取消关注

## 4.4.4 Venues
- 关注的期刊 / 会议来源
- 最近更新

## 4.4.5 Queries
将 `Saved Search` 升级为 `Query Subscription`：
- query name
- query text
- filters
- active state
- recent hits

## 4.4.6 Recent Hits
- 时间排序
- 命中来源（author / venue / query）
- 一键入 Inbox / Queue / Collection

---

# 4.5 Settings 页面线框

## 4.5.1 页面目标
定义系统如何为用户服务，而不是承担日常任务流。

## 4.5.2 页面结构

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Nav                                                     │
├──────────────────────────────────────────────────────────────┤
│ Page Header: Settings / 偏好与配置                           │
├──────────────────────────────────────────────────────────────┤
│ Tabs: Profile | Sources | Ranking | System                  │
├──────────────────────────────────────────────────────────────┤
│ Form Sections / Save / Trigger Refresh                      │
└──────────────────────────────────────────────────────────────┘
```

## 4.5.3 Profile
- core keywords
- secondary keywords
- dislike / demote keywords
- theory preference

## 4.5.4 Sources
- Zotero 路径
- Zotero 启用状态
- arXiv categories

## 4.5.5 Ranking
- papers_per_day
- semantic similarity on/off
- ranking emphasis weights（可后置）

## 4.5.6 System
- cache status
- latest job
- 导入/导出本地状态

---

## 5. 组件与交互规范

# 5.1 必须统一的组件
建议统一以下组件并复用，不允许页面各自生长独立样式：
- `AppShell`
- `TopNav`
- `PageHeader`
- `SectionCard`
- `ListItem`
- `DetailPanel`
- `ActionButton`
- `FilterChip`
- `StatusChip`
- `Modal`
- `Drawer`
- `EmptyState`
- `Toast`

# 5.2 必须统一的状态标签
统一为：
- Relevant
- Ignored
- Inbox
- Skim Later
- Deep Read
- Saved
- Archived

不得在不同页面中混用：
- liked
- favorite
- relevant
- saved

如果语义不同，必须重新命名；如果语义相同，必须统一名称。

# 5.3 创建 Collection 的标准交互

### 入口
- 来自 Queue
- 来自 Library
- 来自 Inbox 的 More actions

### 流程
1. 点击“加入 Collection”
2. 弹出 modal/drawer
3. 展示已有 Collections
4. 支持新建 Collection
5. 新建字段：name / description / optional seed query
6. 确认后加入当前 paper
7. toast 反馈成功

# 5.4 首页 More actions 的标准内容
建议包含：
- Add to Collection
- Download PDF
- Export BibTeX
- View full explanation

禁止把这些动作都放在列表项主按钮行中。

---

## 6. 前端重构任务拆解

# 6.1 IA 与导航重构
### Task 1
重构一级导航为：
- Inbox
- Queue
- Library
- Monitor
- Settings

### Task 2
移除 Search 作为一级主导航，改为上下文能力。

### Task 3
重新定义每个页面的 header 文案与职责。

---

# 6.2 Inbox 重构
### Task 4
瘦身首页，只保留 triage 相关模块。

### Task 5
移除首页中过多资产与追踪摘要入口。

### Task 6
重构右侧 detail panel，仅保留一级决策动作 + More actions。

### Task 7
将 why_above / why_hidden 从默认展示降级为展开项。

### Task 8
统一 paper list item 的高度规则和信息密度。

---

# 6.3 Queue 重构
### Task 9
新增独立 Queue 页面骨架。

### Task 10
实现按状态切换的队列视图。

### Task 11
支持 note 编辑与状态迁移。

---

# 6.4 Library 重构
### Task 12
新增 Library 页骨架与 tab：Collections / Saved Papers / History。

### Task 13
实现 Collection 列表与详情视图。

### Task 14
将 prompt 式 collection 创建改为 modal/drawer。

### Task 15
实现 Saved Papers 子页。

### Task 16
实现 History 的回看与再入队操作。

---

# 6.5 Monitor 重构
### Task 17
新增 Monitor 页面骨架。

### Task 18
把 scholar/journal/query tracking 统一到 Monitor 中。

### Task 19
将 Saved Search 改名并升级为 Query Subscription。

### Task 20
实现 Recent Hits 聚合区。

---

# 6.6 Settings 重构
### Task 21
将关键词管理、数据源管理、排序偏好收口到 Settings。

### Task 22
重构 Settings 为 tab 化表单界面。

### Task 23
保存设置时走统一 job 流程，而不是分散触发不同刷新模式。

---

# 6.7 组件系统重构
### Task 24
提炼统一组件样式和 spacing scale。

### Task 25
减少页面级魔法数、min-height、局部 calc 依赖。

### Task 26
统一 empty state / modal / chip / panel 的视觉规则。

---

## 7. 后端与状态层重构任务

# 7.1 数据模型统一
### Task 27
梳理 canonical entities：Paper / QueueItem / Collection / Subscription / InteractionEvent。

### Task 28
减少 Markdown/JSON 反向拼装 UI 的路径。

### Task 29
让 SQLite 状态层成为前端主要读取来源。

# 7.2 服务层拆分
### Task 30
从 `web_server.py` 中抽出：
- recommendation_service
- queue_service
- library_service
- monitor_service
- settings_service

### Task 31
建立 `viewmodels/` 层，负责模板展示对象构造。

### Task 32
统一 job 创建与状态更新逻辑。

---

## 8. 建议的开发顺序（推荐实际执行路线）

## 阶段 A：页面骨架先行
1. 改导航
2. 新建 Queue / Library / Monitor / Settings 基础页
3. 首页去掉多余模块

## 阶段 B：关键交互替换
4. Collection modal 替换 prompt
5. More actions 收纳次级动作
6. Query Subscription 命名与入口调整

## 阶段 C：数据层收束
7. 统一状态读取来源
8. 抽 service / viewmodel
9. 清理旧静态 HTML 路线依赖

## 阶段 D：视觉统一
10. 修 spacing
11. 修对齐
12. 修组件细节
13. 做移动端和窄屏适配

---

## 9. AI agent / Codex 实施建议

如果后续交给 AI agent 执行，建议拆成多个小 PR，而不是一次性大重构。

### 推荐拆分方式

#### PR 1：导航与页面骨架
- 新导航
- 新页面模板占位
- 不动业务逻辑

#### PR 2：Inbox 瘦身
- 首页减法
- More actions
- detail panel 降噪

#### PR 3：Collection 交互改造
- modal/drawer
- remove prompt
- add to collection flow

#### PR 4：Queue 页面
- 队列视图
- 状态迁移
- note

#### PR 5：Library 页面
- Collections
- Saved Papers
- History

#### PR 6：Monitor 页面
- Authors / Venues / Queries / Recent Hits

#### PR 7：Settings 重构
- tab 化设置页
- 统一保存与 job 流程

#### PR 8：后端服务拆层
- services/
- viewmodels/
- reduce web_server.py size

#### PR 9：设计系统统一
- spacing scale
- chips / panels / modal / empty state
- alignment cleanup

---

## 10. 最小可交付版本定义（MVP of redesign）

以下能力完成后，即可认为“产品重设计第一阶段”达标：

1. 新导航已经落地
2. Inbox 已收束为 triage 主线
3. Queue 有独立页面
4. Library 有 Collections + Saved Papers
5. Monitor 有 Authors + Queries
6. Settings 有 Profile + Sources
7. Collection 创建已不再使用 prompt
8. Search 不再是顶层主导航
9. 首页模块明显减少、主次清楚
10. 主要页面共享统一组件风格

---

## 11. 收尾建议

### 11.1 哪些问题不要过早纠结
在信息架构收束前，不要花太多时间在：
- 某个 chip 再微调 2px
- 某个面板再换一个渐变
- 某个卡片阴影再弱一点

这些问题在页面职责不稳时会反复返工。

### 11.2 真正优先级最高的问题
真正优先级最高的是：
- 首页到底只做什么
- 哪些功能属于 Queue
- 哪些功能属于 Library
- 哪些功能属于 Monitor
- 哪些动作是一级动作，哪些动作是二级动作

只要这个问题解决了，前端“看起来不对齐”的问题会自然减少一大半。

---

## 12. 一句话执行结论

本轮重构不是“再做一个更花的前端”，而是：

> 先把产品收束成一个以 Inbox 为核心的 research triage desk，再用统一组件系统把它做稳。
