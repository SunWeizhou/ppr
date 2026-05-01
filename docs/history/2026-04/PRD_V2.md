# PRD v2：Personalized Paper Recommender / Research Triage Desk

## 1. 文档信息

- 产品名称：Paper Recommender / Research Triage Desk
- 仓库：SunWeizhou/ppr
- 文档版本：v2.0
- 产品类型：local-first personalized research triage desk
- 核心用户：统计学、机器学习、深度学习、RAG / GraphRAG 方向研究者
- 文档目的：
  - 重新定义论文推荐系统的产品目标、功能边界和工程实施约束
  - 约束 Codex 不要继续堆功能，而是围绕核心用户流做产品化
  - 明确哪些功能必须保留，哪些功能应该隐藏，哪些功能暂不开发

---

## 2. 产品重新定义

### 2.1 产品一句话定义

本系统不是普通 arXiv RSS，也不是通用文献搜索器，而是一个面向个人研究者的 **local-first personalized research triage desk**。

它应该帮助用户每天回答五个问题：

1. 今天有哪些论文值得我看？
2. 这篇论文讲了什么？
3. 为什么系统把这篇论文推荐给我？
4. 我应该忽略、略读、精读，还是长期保存？
5. 我关注的作者、期刊、会议和研究问题最近有什么新进展？

### 2.2 产品核心价值

不是“给用户更多论文”，而是：

> 根据用户研究兴趣、Zotero 文献库、历史反馈、阅读行为和长期订阅对象，推荐真正值得处理的论文，并在系统内提供摘要、AI 分析、推荐原因和下一步阅读动作。

### 2.3 产品核心能力

本产品必须围绕以下四项能力构建：

1. **个性化推荐**
   - 根据用户研究画像、历史行为、Zotero、Collection、Subscription 推荐论文。

2. **系统内理解论文**
   - 用户不需要跳到 arXiv 才能判断论文价值。
   - 系统内必须展示论文摘要、AI 分析、推荐原因。

3. **阅读流程管理**
   - 将论文分为 Ignore / Skim Later / Deep Read / Saved / Archived。
   - Queue 是阅读流程，不是另一个推荐页面。

4. **长期追踪**
   - 用户可以追踪指定作者、指定期刊/会议、指定研究问题。
   - Monitor 是核心功能，不应删除。

---

## 3. 产品设计原则

### 3.1 Local First

用户数据默认保存在本地：

- 用户研究画像
- 历史反馈
- Queue 状态
- Collections
- Subscriptions
- AI 分析缓存
- 推荐历史
- 评估报告

不引入账号系统，不引入云同步，不要求用户上传私人文献库。

### 3.2 Inbox First

首页只服务每日论文分拣。

Inbox 中的核心任务是：

```text
看论文 → 理解论文 → 理解推荐原因 → 做阅读决策

首页不应该承载复杂配置、PDF 管理、BibTeX 导出、调试面板、复杂追踪配置。

3.3 Explainable Recommendation

每篇论文必须回答：

为什么推荐给我？

推荐原因不能只显示一个分数，应该结构化展示：

命中了哪些研究主题
来自哪个作者 / 期刊 / query 订阅
是否与 Zotero 文献库相似
是否与历史喜欢论文相似
是否符合理论偏好
是否被用户过去行为强化
3.4 AI-Assisted, Not AI-Dependent

AI 分析是核心体验，但系统不能依赖 AI 才能运行。

如果用户没有配置 AI provider：

仍然显示原始摘要
仍然显示规则推荐原因
AI Analysis 区域显示 fallback message
不阻塞推荐 pipeline
3.5 Progressive Disclosure

默认界面保持简单。

高级功能应隐藏在二级入口或 Advanced 中：

PDF 下载
BibTeX 导出
ranking diagnostics
citation analysis
evaluation reports
demote / dislike / theory signal 细调
source weights
3.6 Subscription Is Core

作者、期刊/会议、研究问题追踪是核心能力，不应删除。

但它们应该统一为简单的 Subscription 模型，而不是每类对象各自生长复杂页面。

4. 目标用户
4.1 核心用户
应用统计 / 机器学习 / 深度学习方向本科生、硕士、博士
每天需要浏览 arXiv / conference / journal 新论文的研究者
有明确研究方向和长期问题意识
使用 Zotero 或本地 PDF 管理文献
希望减少信息过载，而不是看到更多论文
4.2 用户典型场景
场景 1：每日论文分拣

用户打开系统，希望快速知道今天哪些论文值得看。

场景 2：理解推荐原因

用户看到一篇论文，希望知道它为什么被推荐：

是因为关键词？
是因为 Zotero 相似？
是因为订阅作者？
是因为研究问题 query？
是因为自己过去喜欢类似论文？
场景 3：快速理解论文

用户不想每篇都打开 arXiv，希望系统内直接看到：

原始摘要
AI 总结
方法概括
贡献和局限
阅读建议
场景 4：长期追踪研究方向

用户希望长期追踪：

指定作者
指定期刊 / 会议
指定研究问题
场景 5：沉淀研究资产

用户希望把真正重要的论文放进 Collection，并围绕研究问题长期积累。

5. 非目标

当前阶段不做：

多人协作
账号系统
云同步
社交推荐
复杂 citation graph
自动综述论文生成
多设备同步
浏览器插件
桌面客户端
大型前后端分离重写
复杂 agent research assistant

这些可以作为未来方向，但不得干扰当前产品闭环。

6. 信息架构

一级导航保留五页：

Inbox / Queue / Library / Monitor / Settings
6.1 Inbox

每日论文分拣中心。

核心问题：

今天哪些论文值得我处理？
6.2 Queue

阅读流程管理。

核心问题：

我接下来应该读什么？
6.3 Library

长期研究资产库。

核心问题：

哪些论文已经变成我的长期研究资产？
6.4 Monitor

长期追踪中心。

核心问题：

我关注的作者、期刊、会议、研究问题最近有什么新论文？
6.5 Settings

系统偏好与本地配置。

核心问题：

系统应该如何为我推荐论文？
7. 核心对象模型
7.1 Paper

论文实体。

字段建议：

id
title
authors
abstract
categories
published_at
updated_at
source
source_url
pdf_url
7.2 RecommendationRun

一次推荐批次。

字段建议：

id
date
trigger_source
paper_count
status
created_at
finished_at
7.3 RecommendedPaper

某次推荐中的论文及其推荐信息。

字段建议：

run_id
paper_id
rank
score
reason_summary
matched_topics_json
matched_subscriptions_json
zotero_similarity
feedback_signals_json
source_tags_json
7.4 PaperAIAnalysis

论文 AI 分析缓存。

字段建议：

paper_id
one_sentence_summary
problem
method
contribution
limitations
why_it_matters
reading_recommendation
model_name
prompt_version
created_at
updated_at
7.5 QueueItem

阅读流程状态。

字段建议：

paper_id
status: Inbox / Skim Later / Deep Read / Saved / Archived
note
tags_json
source
updated_at
7.6 Collection

长期研究资产容器。

字段建议：

id
name
description
seed_query
notes
created_at
updated_at
7.7 CollectionPaper

Collection 与论文关系。

字段建议：

collection_id
paper_id
note
added_at
7.8 Subscription

统一追踪对象。

字段建议：

id
type: query / author / venue
name
query_text
payload_json
enabled
last_checked_at
latest_hit_count
created_at
updated_at
7.9 SubscriptionHit

订阅命中结果。

字段建议：

subscription_id
paper_id
matched_reason
hit_date
status: new / sent_to_inbox / queued / ignored
created_at
7.10 InteractionEvent

用户行为事件。

字段建议：

id
event_type
paper_id
payload_json
created_at

事件类型包括：

paper_opened
feedback_relevant
feedback_ignored
queue_status_changed
added_to_collection
subscription_created
subscription_hit_queued
ai_analysis_generated
8. 页面详细设计
8.1 Inbox
8.1.1 页面目标

让用户在最短时间完成：

看摘要 → 看 AI 分析 → 看推荐原因 → 做阅读决策
8.1.2 页面必须展示

每篇论文详情面板必须包含：

Title
Authors
Source tags
Abstract
AI Analysis
Why Recommended
Actions
8.1.3 AI Analysis 区域

结构固定为：

AI Analysis
- 一句话总结
- 研究问题
- 方法思路
- 主要贡献
- 局限性
- 为什么重要
- 阅读建议

阅读建议只能是：

Ignore / Skim Later / Deep Read / Saved
8.1.4 Why Recommended 区域

结构固定为：

Why Recommended
- Matched topics
- Matched subscriptions
- Zotero similarity
- Feedback signals
- Source reason

展示方式应该是自然语言 + chips，不要直接展示复杂 JSON。

8.1.5 Inbox 主操作

只保留：

Relevant
Ignore
Skim Later
Deep Read
Open arXiv
8.1.6 Inbox 二级操作

只保留：

Add to Collection
View full explanation
8.1.7 Inbox 禁止直接展示
Download PDF
Export BibTeX
Follow author
Archive
Full diagnostics
Ranking breakdown
Citation graph
Batch engineering tools

这些功能可保留在 Queue / Library / Advanced 中。

8.1.8 Inbox 完成状态

需要支持今日分拣闭环：

Today: 20 papers
Handled: 12
Untriaged: 8
Queued: 4
Ignored: 6

提供：

Finish today

点击后显示今日总结：

今天已处理 X 篇论文，Y 篇进入阅读队列，Z 篇被忽略。
8.2 Queue
8.2.1 页面目标

Queue 负责阅读流程，不负责重新推荐论文。

核心问题：

我接下来应该读什么？
8.2.2 状态定义
Inbox       已进入系统但尚未处理
Skim Later  稍后快速浏览
Deep Read   需要认真阅读
Saved       长期保留
Archived    已处理完或暂不关注
8.2.3 Queue 页面必须包含
状态筛选
论文列表
论文摘要
AI Analysis
note
Move To
Open arXiv
PDF
Add to Collection
8.2.4 Queue 默认视图

新增：

Today's Reading Plan

默认展示：

前 3 篇 Deep Read
前 5 篇 Skim Later

帮助用户从“收藏很多论文”变成“今天知道读什么”。

8.3 Library
8.3.1 页面目标

Library 是长期研究资产库，不是临时收藏夹。

8.3.2 保留
Collections
Saved Papers
8.3.3 弱化
History

History 只能作为回看入口，不作为一级核心体验。

8.3.4 Collection 必须支持

每个 Collection 是一个研究问题容器。

字段：

name
description
seed_query
notes
papers

Collection 页面应支持：

Research Question
Why this topic matters
Key Papers
Open Questions
Next Reading Target

这些可以先手动填写，不要求 AI 自动生成。

8.4 Monitor
8.4.1 页面目标

Monitor 是长期追踪中心，不能删除。

核心问题：

我关注的作者、期刊、会议、研究问题最近有什么新论文？
8.4.2 Monitor 结构
Research Questions
Authors
Venues
Recent Hits
8.4.3 Research Questions

最重要的订阅类型。

例子：

GraphRAG compression
prompt compression for multi-hop QA
agentic RAG
financial report GraphRAG
conformal prediction
transformer theory

每个 Research Question 本质是 query subscription。

8.4.4 Authors

用户可追踪指定作者。

字段：

name
affiliation
query_text
profile_url
enabled

MVP 不需要复杂作者画像。

8.4.5 Venues

用户可追踪指定期刊 / 会议。

字段：

name
type: journal / conference
source_url or venue_key
enabled

MVP 不需要复杂 volume / issue 浏览。

8.4.6 Recent Hits

聚合所有订阅命中。

每条 hit 支持：

View detail
Send to Inbox
Skim Later
Deep Read
Add to Collection
Ignore
8.5 Settings
8.5.1 页面目标

Settings 只负责配置系统如何为用户服务。

8.5.2 默认展示

只展示：

Research Topics
Daily Paper Count
Zotero Path
AI Analysis Provider
Backup / Restore
8.5.3 Advanced 中展示

隐藏到 Advanced：

demote topics
dislike topics
theory signals
ranking weights
journal source config
scholar source config
evaluation reports
cache/debug information
9. AI Analysis 设计
9.1 基本原则

AI Analysis 是核心体验，但必须：

可缓存
可失败
可关闭
不阻塞推荐 pipeline
不要求真实 API 才能跑测试
9.2 AI Analysis Service

新增：

app/services/ai_analysis_service.py

接口建议：

class AIAnalysisService:
    def get_or_create_analysis(self, paper, user_profile, recommendation_context):
        ...
9.3 Provider 设计

支持：

NoProvider
FakeProvider
OpenAICompatibleProvider

测试只使用 FakeProvider，不使用真实 API key。

9.4 缓存策略

以 canonical arXiv ID 作为 key。

同一篇论文如果已有 analysis，直接返回缓存。

除非：

prompt_version 变化
用户手动 regenerate
analysis 为空或损坏
9.5 AI Prompt 输出格式

AI provider 必须返回结构化 JSON：

{
  "one_sentence_summary": "",
  "problem": "",
  "method": "",
  "contribution": "",
  "limitations": "",
  "why_it_matters": "",
  "recommended_reading_level": "skim"
}
10. 推荐原因设计

每篇推荐论文必须有结构化推荐原因：

{
  "reason_summary": "",
  "matched_topics": [],
  "matched_subscriptions": [],
  "zotero_similarity": null,
  "feedback_signals": [],
  "source_tags": []
}

页面展示时转为自然语言：

推荐原因：
- 命中你的核心主题：GraphRAG compression
- 来自你的研究问题订阅：prompt compression for multi-hop QA
- 与 Zotero 中 3 篇论文语义相似
- 你过去将类似论文加入过 Deep Read
11. Onboarding
11.1 目标

新用户不应该手动编辑 JSON。

首次启动必须提供 onboarding。

11.2 触发条件

当缺少有效 user_profile.json 或 profile 没有正向研究主题时，进入 onboarding。

11.3 Onboarding 步骤
Step 1: 研究主题
Step 2: 每日推荐数量
Step 3: Zotero 配置
Step 4: AI Analysis 配置
Step 5: 创建第一个 Research Question Subscription
11.4 完成后

保存 profile，进入 Inbox，并提示用户生成今日推荐。

12. 功能优先级
P0：必须做
Inbox 展示 Abstract + AI Analysis + Why Recommended
AI Analysis 本地缓存
推荐原因结构化
Query / Author / Venue Subscription 统一模型
Monitor 保留 Research Questions / Authors / Venues / Recent Hits
First-run onboarding
Inbox 首页去除 PDF / BibTeX / Follow author / Archive 等干扰动作
Queue 保持阅读流程
Collection 作为研究问题容器
所有新功能必须有测试
P1：应该做
Today's Reading Plan
Finish today
Collection notes
Recent Hits 一键入队
AI analysis regenerate
Subscription disable / enable
Export / Import state 改进
推荐效果 evaluation 与反馈闭环
P2：延后
citation graph
LLM 自动综述
多设备同步
云同步
账号系统
浏览器插件
桌面客户端
社交推荐
复杂作者画像
复杂期刊卷期浏览
13. Codex 开发约束
13.1 禁止行为

Codex 不得：

一次性重写整个项目
引入大型前端框架
引入账号系统
引入云同步
删除 Authors / Venues / Query Subscriptions
删除现有用户数据
让真实 API key 成为测试前提
把 AI 分析写成必须联网才能运行的功能
在 Inbox 中重新堆满 PDF / BibTeX / debug / diagnostics
把 JSON / Markdown 重新变成主数据源
13.2 必须行为

Codex 必须：

小 PR 迭代
每个 PR 有测试
保持 local-first
保持旧数据兼容
新增 service 层时避免直接 import web_server
UI 行为保持简单
所有 AI 能力提供 no-provider fallback
所有 paper_id 使用 canonical arXiv ID
所有用户行为写入 InteractionEvent
14. 推荐实施路线
PR 1：Inbox Simplification + AI Analysis Placeholder

目标：

让 Inbox 变成“摘要 + AI 分析 + 推荐原因 + 分拣动作”。

交付：

移除 Inbox 主界面的 PDF / BibTeX / Follow author / Archive
增加 AI Analysis 区域
增加 Why Recommended 结构化展示
保留 Relevant / Ignore / Skim Later / Deep Read / Open arXiv
PR 2：AI Analysis Service + Cache

目标：

建立本地可缓存的 AI 分析能力。

交付：

paper_ai_analyses 表
AIAnalysisService
FakeProvider
NoProvider fallback
API endpoint
测试
PR 3：Unified Subscription Model

目标：

统一 Research Questions / Authors / Venues。

交付：

subscriptions 表
subscription_hits 表
Monitor 改为统一模型
saved_searches 兼容迁移
测试
PR 4：First-run Onboarding

目标：

让新用户不编辑 JSON 也能开始使用。

交付：

onboarding 页面
profile 创建
Zotero 配置
AI provider 配置
初始 query subscription 创建
测试
PR 5：Recommendation Reason Refactor

目标：

让推荐原因结构化、可解释、可展示。

交付：

reason_summary
matched_topics
matched_subscriptions
zotero_similarity
feedback_signals
source_tags
前端展示
测试
15. 成功标准

产品达到可用状态时，应满足：

新用户无需编辑 JSON 即可开始使用。
用户打开 Inbox 后能直接看到今日推荐论文。
每篇论文都有摘要、AI 分析和推荐原因。
用户能快速标记 Relevant / Ignore / Skim Later / Deep Read。
用户能追踪研究问题、作者、期刊/会议。
Monitor 能聚合订阅命中。
Queue 能形成阅读计划。
Library 能沉淀长期研究资产。
所有状态保存在本地。
没有 AI provider 时系统仍可正常使用。