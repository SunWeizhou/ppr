# PRD：本地优先论文推荐工作台（Paper Recommender / Research Triage Desk）

## 1. 文档信息

- 产品名称：Paper Recommender / Research Triage Desk
- 仓库：`SunWeizhou/ppr`
- 文档版本：v1.0
- 文档目的：对当前论文推荐系统进行一次从产品定位、信息架构、功能分层到前端交互的整体重设计，作为后续代码重构、页面改版和迭代规划的统一依据。

---

## 2. 背景与问题

当前系统已经具备较强的能力基础：
- 从 arXiv 获取论文并进行排序推荐
- 结合 Zotero、关键词、语义相似度和用户反馈做个性化推荐
- 支持阅读队列、收藏、搜索、学者追踪、期刊追踪、历史记录和本地持久化

但系统目前存在两个核心问题：

### 2.1 前端问题
新版前端已经有“研究工作台”的雏形，但存在以下明显问题：
- 模块对齐不稳定，页面细节依赖大量定高、sticky 和局部补丁维持整齐
- 首页承载过多功能，信息密度过高，主次关系不清
- 同类模块的视觉规则不完全统一，导致页面看起来像“正在演化中的内部工具”而不是稳定产品
- 局部交互仍偏工程化，例如通过 prompt 创建 collection，而不是完整的产品级面板流程

### 2.2 产品问题
系统功能很多，但尚未形成清晰的层级关系：
- 发现论文、管理阅读流程、沉淀研究资产、监控外部更新这几类任务被混在同一层
- 首页、搜索、追踪、收藏、喜欢、saved search 等概念边界不清
- 部分能力已经有底层状态模型，但前台页面没有围绕这些模型构建稳定的用户路径

### 2.3 结论
当前产品的主要矛盾不是“功能不够”，而是“功能太杂且没有收束成清晰主线”。

因此，本次 PRD 的目标不是继续堆功能，而是：

> 将当前系统重构为一个以 **论文分拣（triage）** 为核心主线、以 **本地优先（local-first）** 为基本原则、以 **研究工作流** 为设计对象的论文推荐工作台。

---

## 3. 产品定位

### 3.1 产品定义
一个面向统计学 / 机器学习研究者的 **local-first research triage desk**，帮助用户每天快速判断：
- 今天哪些论文值得处理
- 这些论文应该进入哪个阅读层级
- 哪些内容需要长期沉淀为研究资产
- 哪些作者 / 期刊 / 问题需要持续追踪

### 3.2 一句话价值
不是“给你更多论文”，而是“帮助你更快地决定今天先读什么，并把值得保留的内容沉淀成长期研究资产”。

### 3.3 核心设计原则
1. **Inbox First**：首页只服务于“今日论文分拣”这一主任务。
2. **Local First**：用户状态和数据优先保存在本地，保证可控、可持续、可迁移。
3. **Action over Browsing**：强调决策和动作，而不是被动浏览卡片。
4. **Asset Thinking**：论文不是一次性信息流，而是长期研究资产的来源。
5. **Progressive Disclosure**：高级能力可以存在，但不应该全部挤在首屏。
6. **Single Source of Truth**：避免 Markdown、JSON、SQLite 多处充当主数据源。

---

## 4. 目标用户

### 4.1 核心用户
- 应用统计、机器学习、深度学习方向本科生 / 研究生 / 博士生
- 高频阅读 arXiv / conference preprint 的研究者
- 有明确研究主题，希望构建长期论文工作流的人

### 4.2 用户特征
- 每天需要处理一定量的新论文
- 研究兴趣有偏好，不想看无关论文
- 需要把论文分层：快速 skim、深入阅读、长期收藏
- 已有 Zotero / PDF / BibTeX / 关键词管理等习惯
- 希望推荐系统解释“为什么推荐”，而不是黑箱排序

### 4.3 非目标用户
- 完全轻度的偶尔搜一篇论文的普通用户
- 需要海量团队协作、多人权限管理的大型实验室场景
- 需要通用文献数据库替代品的用户

---

## 5. 产品目标与非目标

### 5.1 产品目标
本版本重设计的目标：
1. 明确产品主线，解决功能杂乱问题
2. 重构信息架构，建立清晰的顶层导航和页面职责
3. 降低首页认知负担，让用户在 3 分钟内完成一轮今日论文分拣
4. 建立统一的前端设计系统，解决布局和细节不稳问题
5. 把已有底层能力收敛成可长期维护的产品结构

### 5.2 非目标
本版本不追求：
- 多人协作和账号系统
- 云端同步优先
- 极其复杂的社交发现功能
- 学术图谱 / 大模型问答 / 自动综述生成等重能力
- 面向大众用户的消费级推荐产品形态

---

## 6. 产品总览：新的信息架构

## 6.1 顶层结构
新的产品结构统一为 5 个一级页面：

1. **Inbox**：今日论文分拣中心
2. **Queue**：阅读流程与队列管理
3. **Library**：长期研究资产库
4. **Monitor**：作者 / 期刊 / 问题订阅监控
5. **Settings**：研究画像与系统设置

### 6.2 Search 的新定位
Search 不再作为独立的一号核心页面，而是一个横向能力：
- 在 Inbox 中用于“围绕当前主题继续探索”
- 在 Library 中用于“在已有资产中检索”
- 在 Monitor 中以 Saved Search / Query Subscription 的形式长期存在

即：
- “搜索”是能力
- “订阅问题”是产品对象
- “探索相关内容”是上下文动作

### 6.3 四大核心对象
本产品围绕以下 4 个对象组织：
- **Paper**：论文实体
- **Queue Item**：阅读层级状态
- **Collection**：研究资产容器
- **Subscription**：监控对象（作者 / 期刊 / 查询）

用户的大部分行为都应该落到这四类对象之一上。

---

## 7. 页面与功能设计

# 7.1 Inbox（首页）

### 7.1.1 页面目标
用户打开产品后，能在最短时间完成：
- 浏览今日候选论文
- 理解为什么推荐
- 对论文做出最小必要决策

### 7.1.2 主页核心任务
首页只保留 3 个核心动作：
1. 标记为 relevant / ignore
2. 加入某个阅读层级（Skim Later / Deep Read）
3. 打开原文

### 7.1.3 首页不再作为主要入口承载的动作
以下能力不应在首页占据高权重位置：
- 创建 collection
- 导出 BibTeX
- 下载 PDF
- 复杂追踪配置
- 过多的资产管理入口
- 过深的 ranking diagnostics

这些能力仍然保留，但降级到二级操作或其他页面。

### 7.1.4 页面布局
建议采用三栏结构，但重新收束职责：

#### 左栏：Context Rail
展示轻量上下文，不喧宾夺主：
- 日期切换
- 今日主题摘要
- 筛选 chip（All / Untriaged / Queued / Relevant / Ignored）
- 生成状态摘要

#### 中栏：Paper List
首页核心区域：
- 今日排序后的论文列表
- 每项显示：标题、作者、类别、摘要短句、score、状态标签
- 点击后更新右侧 detail
- 支持键盘上下切换

#### 右栏：Decision Panel
聚焦单篇论文的决策：
- 标题、作者、摘要
- Why recommended
- relevant / ignore
- Queue 到 Skim Later / Deep Read
- Open arXiv
- More actions（弹层或下拉）

### 7.1.5 首页模块优先级
P0 模块：
- 今日推荐列表
- 筛选
- 单篇详情
- relevant / ignore
- Queue 动作
- 打开原文

P1 模块：
- 为什么推荐
- 简短的排序解释
- 历史日期切换

P2 模块：
- 详细 why above / why hidden
- 调试型指标
- 深层 ranking 分解

### 7.1.6 首页成功标准
用户在首页应能做到：
- 30 秒内理解页面主任务
- 1 分钟内处理前 3 篇论文
- 3 分钟内完成一轮今日初筛

---

# 7.2 Queue

### 7.2.1 页面目标
把 Inbox 中做出的决定，转化为真正的阅读流程。

### 7.2.2 队列状态
保留并明确语义：
- **Inbox**：已进入系统但未处理
- **Skim Later**：需要快速浏览
- **Deep Read**：需要精读
- **Saved**：长期保留但不一定近期读
- **Archived**：不再关注，但保留记录

### 7.2.3 页面布局
建议为看板或两栏列表页：
- 左侧为状态分组
- 右侧为选中论文详情与操作

### 7.2.4 核心操作
- 调整队列状态
- 添加 note
- 标记完成 / 归档
- 打开原文 / PDF
- 加入 Collection

### 7.2.5 设计原则
Queue 页面应体现“阅读流程”，而不是再次做推荐浏览。

---

# 7.3 Library

### 7.3.1 页面目标
把已经确认有价值的论文沉淀为长期研究资产。

### 7.3.2 子模块
Library 下分为三个 tab：
1. **Collections**
2. **Saved Papers**
3. **History**

### 7.3.3 Collections
Collection 的新定义：
- 不是“随手收藏夹”
- 而是一个面向研究问题的容器

例子：
- Conformal Prediction
- Transformer Theory
- OOD Detection in FL
- Plankton OOD Baselines

Collection 页面中应支持：
- 查看 collection 列表
- 创建 / 编辑 collection
- 在 collection 中添加 paper
- 给 collection 写 description / query seed / notes
- 按最近更新排序

### 7.3.4 Saved Papers
Saved Papers 用于承接“我确认以后会保留”的论文，和 Queue 中的 Saved 状态一一对应。

### 7.3.5 History
History 用于查看历史推荐批次，不作为主数据源，只作为历史视图和回溯界面。

### 7.3.6 交互要求
禁止继续使用 `window.prompt()` 创建 collection。
必须改为：
- 按钮触发侧边抽屉或 modal
- 表单字段：name / description / optional seed query
- 成功后可直接选择加入当前 paper

---

# 7.4 Monitor

### 7.4.1 页面目标
统一所有“持续关注外部更新”的能力。

### 7.4.2 子模块
Monitor 下统一三类订阅：
1. **Authors**：关注作者
2. **Journals / Venues**：关注期刊或会议来源
3. **Queries**：关注长期研究问题

### 7.4.3 重新命名建议
当前的 Saved Search 更适合升级为：
- Query Subscription
- 或 Topic Monitor

原因：
“Saved Search”听起来像搜索历史，而不是持续订阅对象。

### 7.4.4 页面职责
Monitor 页面主要回答：
- 我在持续关注谁
- 我在持续关注哪些问题
- 最近有哪些新变化

### 7.4.5 核心功能
- 新建作者订阅
- 新建问题订阅
- 新建期刊 / venue 订阅
- 查看最近命中更新
- 一键加入 Inbox / Queue / Collection

### 7.4.6 与首页关系
Monitor 是长期监控页，不应直接干扰首页的今日分拣主线。

---

# 7.5 Settings

### 7.5.1 页面目标
集中管理用户画像、排序偏好和数据源设置。

### 7.5.2 子模块
1. **Research Profile**
   - 核心关键词
   - 次级关键词
   - 降权 / 不喜欢关键词
   - 理论偏好开关
2. **Data Sources**
   - Zotero 路径与启用状态
   - arXiv 类别
3. **Ranking Preferences**
   - 每日论文数
   - 是否启用语义相似度
   - 强调理论 / 作者 / 新颖性
4. **System**
   - 缓存状态
   - 最近 job
   - 导入 / 导出本地状态

### 7.5.3 设计原则
Settings 是“定义系统如何为我服务”的地方，而不是日常高频操作界面。

---

## 8. 前端重设计原则

# 8.1 总体视觉方向
界面风格应继续保留“研究桌面 / paper desk”的气质，但要从“漂亮的 demo”进化为“稳定的产品系统”。

### 8.1.1 风格关键词
- calm
- warm
- academic
- tactile
- low-noise
- structured

### 8.1.2 不追求的方向
- 过度炫技
- 大量玻璃拟态叠加
- 首页过多阴影和高密度视觉元素
- dashboard 化过强，导致论文本身反而退到背景

---

# 8.2 设计系统约束

### 8.2.1 建立统一的页面骨架
所有一级页面统一为：
- Top nav
- 页面标题区（page header）
- 主内容区（single responsibility）
- 二级面板 / 抽屉 / modal

避免每个页面都长出不同的 hero、不同的 summary strip、不同的局部导航。

### 8.2.2 建立统一的组件层级
建议收敛为以下基础组件：
- AppShell
- PageHeader
- SectionCard
- ListItem
- DetailPanel
- ActionBar
- FilterChip
- StatusChip
- Modal / Drawer
- EmptyState
- Toast

### 8.2.3 建立统一的间距规则
建议定义固定 spacing scale，例如：
- 8 / 12 / 16 / 20 / 24 / 32

禁止页面内大量使用“为了对齐临时加一个 min-height / margin-top / calc()”的方式修补。

### 8.2.4 建立统一的密度规则
首页列表项必须高度可预测，但不能靠过多强行定高。
原则：
- 标题最多 2 行
- 作者最多 2 行
- 摘要最多 3 行
- 元信息固定单行或双行

### 8.2.5 建立统一的状态表达
同一种状态必须在所有页面保持同一语言和视觉：
- Relevant
- Ignored
- Skim Later
- Deep Read
- Saved
- Archived

不要在不同页面里一会儿叫 liked，一会儿叫 saved，一会儿叫 relevant。

---

# 8.3 关键交互要求

### 8.3.1 首页交互
- 点击列表项即可切换右侧详情
- 支持键盘导航
- relevant / ignore 按钮必须始终可见
- Queue 按钮必须简洁明确
- More actions 收纳次级操作

### 8.3.2 次级动作收纳
首页不直接暴露全部动作。
以下动作统一进入“More actions”：
- 加入 Collection
- 下载 PDF
- 导出 BibTeX
- 查看完整 ranking diagnostics

### 8.3.3 创建 Collection
必须替换 prompt 为 modal / drawer。
流程：
1. 点击“加入 Collection”
2. 弹出选择器：已有 collection + 新建 collection
3. 若新建，则填写 name / description / optional seed query
4. 确认后加入当前论文

### 8.3.4 解释信息分层
排序解释分三层：
- L1：Why recommended（首页直接看）
- L2：Why above / hidden（需要展开）
- L3：完整分数 breakdown（调试或高级用户页）

---

## 9. 功能优先级（P0 / P1 / P2）

# 9.1 P0：必须做
这些能力构成新产品闭环的最小可用版本。

### 9.1.1 产品结构
- 一级导航重构为 Inbox / Queue / Library / Monitor / Settings
- 首页降噪，收束为 triage 主线
- Search 从顶层主导航降级为上下文能力

### 9.1.2 Inbox
- 今日推荐列表
- 筛选（All / Untriaged / Relevant / Ignored / Queued）
- 单篇 detail panel
- relevant / ignore
- Queue 到 Skim Later / Deep Read
- 打开 arXiv
- 基础 why recommended

### 9.1.3 Queue
- 队列状态页
- 调整状态
- note
- 打开原文
- 加入 Collection

### 9.1.4 Library
- Collections 列表
- 创建 / 编辑 Collection
- Saved Papers
- 基本 History

### 9.1.5 Monitor
- 作者订阅
- Query Subscription
- 最近命中列表

### 9.1.6 Settings
- 关键词画像管理
- Zotero / arXiv 数据源配置
- papers_per_day 等基础偏好

---

# 9.2 P1：应该做
### 9.2.1 首页增强
- 快捷键支持
- 批量处理
- 更强的解释信息层级

### 9.2.2 Queue / Library 增强
- note 编辑
- tag
- collection 内筛选
- collection 级别描述和 query seed

### 9.2.3 Monitor 增强
- 期刊 / venue 订阅
- 命中结果一键入 Inbox
- 订阅活跃度显示

### 9.2.4 Insights
- 用户偏好变化
- 近期主题分布
- relevant / ignored 比例

---

# 9.3 P2：可以延后
- 更复杂的 ranking diagnostics 页面
- 引用图谱 / 论文关系图
- LLM 综述生成
- 自动阅读摘要卡片
- 多设备同步 / 云端同步
- 社交或团队协作能力

---

## 10. 数据与状态模型重构建议

### 10.1 单一事实来源
需要明确哪些数据是 canonical source：
- 论文实体、队列状态、collection 关系、subscription、interaction event 应进入统一状态层
- Markdown digest 只作为输出视图，不再承担主数据源角色
- 历史 JSON 只作为快照缓存，不再反向参与主要对象拼装

### 10.2 推荐的核心数据对象

#### Paper
- id
- title
- authors
- abstract
- categories
- published_at
- link
- score
- explanation_summary

#### QueueItem
- paper_id
- status
- note
- tags
- updated_at

#### Collection
- id
- name
- description
- seed_query
- is_active
- updated_at

#### CollectionPaper
- collection_id
- paper_id
- note
- added_at

#### Subscription
- id
- type (`author`, `venue`, `query`)
- display_name
- payload
- is_active
- created_at
- updated_at

#### InteractionEvent
- id
- event_type
- paper_id
- payload
- created_at

### 10.3 迁移原则
- 保留现有 SQLite 状态层并继续增强
- 逐步把 JSON 里仍承担“主状态”的内容迁入状态库
- 前端全部围绕状态库读取，而不是拼装 Markdown/JSON 多路结果

---

## 11. 典型用户流程

# 11.1 每日论文分拣流程
1. 用户打开 Inbox
2. 查看今日候选论文列表
3. 点击第一篇论文，右侧展示详情和推荐理由
4. 做出决策：Relevant / Ignore / Queue
5. 连续处理若干篇论文
6. 对值得深入阅读的论文加入 Deep Read
7. 结束当日 triage

### 成功定义
用户完成一轮 triage 后，系统里至少形成以下结果之一：
- relevant / ignored 的显式反馈
- queue 中新增论文
- 若干值得长期保存的论文被送往 Library

# 11.2 论文沉淀流程
1. 用户在 Queue 中打开某篇论文
2. 决定其值得长期保留
3. 选择加入某个 Collection
4. 如无 collection，则创建新 collection
5. 该论文进入对应研究容器

# 11.3 长期问题监控流程
1. 用户在 Monitor 中创建 Query Subscription
2. 输入问题或研究关键词
3. 系统后续抓到相关论文后展示在 Monitor 最近命中列表
4. 用户可将命中项送入 Inbox 或 Queue

---

## 12. 关键文案策略

### 12.1 语言统一原则
建议采用“中文主界面 + 保留少量研究领域约定英文”的方式。

### 12.2 关键状态文案统一
建议统一如下：
- Inbox：待分拣
- Relevant：相关
- Ignored：忽略
- Skim Later：稍后速览
- Deep Read：深入阅读
- Saved：长期保存
- Archived：归档

### 12.3 文案风格
- 少解释系统自己
- 多告诉用户下一步怎么做
- 避免工程术语暴露给用户
- 避免首页出现大量“调试型文案”

---

## 13. 度量指标

### 13.1 北极星指标
- 每日被有效处理的论文数（被标记为 relevant / ignored / queued 的论文数）

### 13.2 一级指标
- 首页 triage 完成率
- Queue 使用率
- Collection 建立与使用率
- Query Subscription 活跃率
- 每日用户有效动作数

### 13.3 二级指标
- 首页首屏停留时间
- 平均每篇论文决策耗时
- relevant / ignored 比例
- Saved / Deep Read 转化率

---

## 14. 里程碑规划

# Milestone 1：产品收束版（优先）
目标：先解决“功能杂乱”和“首页过重”的问题。

交付：
- 新的信息架构
- Inbox / Queue / Library / Monitor / Settings 五页骨架
- 首页减法版
- Collection modal 替换 prompt
- Search 降级为上下文能力

# Milestone 2：状态统一版
目标：减少技术债，收拢主数据源。

交付：
- 明确 canonical data model
- 弱化 Markdown/JSON 作为主数据源的角色
- 强化 SQLite 状态层

# Milestone 3：体验增强版
目标：提高工作台效率和解释性。

交付：
- 快捷键
- 批量操作
- 更好的排序解释层级
- 轻量 insights

# Milestone 4：高级能力探索
目标：在产品主线稳定后再尝试高级功能。

交付方向：
- 主题聚类
- collection 内探索
- 更强的 semantic browsing
- 研究问题级别的长期跟踪

---

## 15. 对当前仓库的具体改造建议

### 15.1 先做减法，不要继续加页面
短期内不要继续新增顶层页面，而要先把现有能力收口。

### 15.2 统一旧前端与新前端
- 逐步退役旧的静态 HTMLGenerator 路线
- 全部收敛到 Flask + 模板 + API + 状态层
- 只保留一套设计系统和一套交互语义

### 15.3 从首页移走这些能力
- 创建 collection
- BibTeX 导出
- PDF 下载
- 深层 ranking 调试
- 过多 monitor 入口

### 15.4 优先重构的代码层
建议优先抽象出以下层次：
- `services/recommendation_service.py`
- `services/library_service.py`
- `services/monitor_service.py`
- `services/queue_service.py`
- `viewmodels/`（负责页面展示模型）
- `templates/`（只关心展示）

避免继续让 `web_server.py` 承载过多职责。

---

## 16. 总结

本次重设计的核心不是“换个更漂亮的前端”，而是：

1. 把系统从“功能堆叠”重构为“主线明确的研究工作流产品”
2. 把首页从“什么都能做”重构为“高效分拣中心”
3. 把收藏、追踪、搜索、历史等能力重新分层
4. 把已有底层状态能力真正变成清晰、统一、稳定的产品对象

最终产品应该让用户感受到的不是：
- 这个系统功能很多

而是：
- 我每天打开它，就知道先处理什么
- 我做出的每个决定都会沉淀成可持续的研究资产
- 它确实理解我的研究方向，而且界面不会打扰我

---

## 17. 附录：建议的新导航

### 顶部一级导航
- Inbox
- Queue
- Library
- Monitor
- Settings

### 每个一级页的核心问题
- Inbox：今天先处理什么？
- Queue：接下来读什么？
- Library：长期留下什么？
- Monitor：外部发生了什么新变化？
- Settings：系统应该如何为我服务？

### 产品最终主线
`Discover -> Decide -> Queue -> Save -> Monitor`

即：
- 发现论文
- 做出决策
- 进入阅读流程
- 沉淀为资产
- 对长期关注对象持续监控
