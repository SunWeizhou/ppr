# Workspace RAG Q&A Design

> 日期：2026-05-14
> 分支：`codex/apple-claude-workspace-redesign`
> 目标：在 workspace 内提供基于已选论文（abstract + AI 分析 + memo）的 RAG 问答，辅助文献综述写作。

---

## 1. 功能概述

用户在 workspace overview 页面手动勾选论文纳入 RAG 索引，然后在问答区提问。系统用 keyword-fingerprint 检索最相关的论文内容，组装 context 交给 AI provider 生成结构化回答。

与现有 Paper Agent 的区别：Agent 是通用对话助手，RAG Q&A 是**专门针对当前 workspace 已勾选论文的知识问答**，默认用检索结果增强 context。

---

## 2. 数据模型

### 2.1 新增字段

`workspace_papers` 表加一列：

```sql
ALTER TABLE workspace_papers ADD COLUMN rag_enabled INTEGER DEFAULT 0;
```

- `rag_enabled = 1`：该论文被用户勾选，纳入 RAG 检索范围
- 默认为 0，需手动勾选

### 2.2 复用已有数据

| 数据 | 来源 | 检索权重 |
|------|------|----------|
| Title + Abstract | `paper_metadata` | 基准 1x |
| AI Analysis | `paper_ai_analyses` | 基准 1x |
| User Memo / Takeaway | `reading_takeaways` / `memos` | 2x（对综述最有价值） |

---

## 3. API 设计

### 3.1 Toggle Paper RAG Status

```
POST /api/rag/toggle
```

**Request:**
```json
{
  "paper_id": "arxiv:2401.12345",
  "research_question_id": 1,
  "rag_enabled": true
}
```

**Response (200):**
```json
{ "success": true, "paper_id": "arxiv:2401.12345", "rag_enabled": true }
```

**Errors:** 400（缺少参数），404（workspace 不存在或 paper 不属于该 workspace）

### 3.2 Ask Question

```
POST /api/rag/ask
```

**Request:**
```json
{
  "research_question_id": 1,
  "question": "这些论文的主要方法可以分为几类？"
}
```

**Response (200):**
```json
{
  "success": true,
  "answer": "基于你选中的 5 篇论文，主要方法可分为...",
  "sources": [
    { "paper_id": "arxiv:2401.12345", "title": "Paper A", "relevance": 0.85 },
    { "paper_id": "arxiv:2402.56789", "title": "Paper B", "relevance": 0.72 }
  ],
  "rag_stats": { "papers_indexed": 5, "papers_retrieved": 3 }
}
```

**Degraded mode（无 AI provider）:**
前端同样拿到 `sources`，自行渲染论文片段。不含 `answer` 字段。
```json
{
  "success": true,
  "answer": "",
  "rag_stats": { "papers_indexed": 5, "papers_retrieved": 3 },
  "sources": [
    { "paper_id": "...", "title": "Paper A", "abstract_preview": "...", "memo_preview": "...", "score": 0.85 },
    { "paper_id": "...", "title": "Paper B", "abstract_preview": "...", "memo_preview": null, "score": 0.72 }
  ]
}
```

**Errors:** 400（缺少参数或 question 为空），400（没有已选论文）

---

## 4. 检索与生成流程

```
POST /api/rag/ask
  │
  ├─ 1. 获取所有 rag_enabled=1 的论文
  │     state_store.list_workspace_papers(rq_id, rag_enabled=True)
  │
  ├─ 2. 为每篇论文构建索引文本
  │     - title + abstract (paper_metadata)
  │     - AI analysis fields (paper_ai_analyses)
  │     - memo / takeaway (memos, reading_takeaways) ← 权重 2x
  │
  ├─ 3. RAG 检索
  │     RagRetrievalService.query(rq_id, question, max_results=5, paper_ids=selected)
  │     → keyword fingerprint cosine similarity
  │
  ├─ 4. 组装 AI prompt
  │     system: "你是文献综述助手。基于以下论文内容回答问题。引用论文时使用标题。"
  │     context: top-K 论文的完整索引文本（总长 ≤ 3000 tokens）
  │     user: question
  │
  └─ 5. 返回
        answer + sources + stats
```

### 4.1 Fallback 路径

- **无 AI provider** → 返回检索结果原文片段
- **检索结果为空** → 提示用户增加勾选论文或换问题
- **AI 调用失败** → 降级为检索片段输出，记录 warning log

---

## 5. 前端改动

### 5.1 Workspace Overview（模板层）

- 论文列表每行加 checkbox：`<input type="checkbox" data-paper-id="..." data-rag-toggle>`
- 列表上方显示："已选 N 篇纳入 RAG"
- 新增 `<section id="rag-qa-section">`：
  - 输入框 + Send 按钮
  - Q&A 历史列表（问题 + AI 回答 + 引用来源）
  - 无 AI 时显示降级提示

### 5.2 JavaScript（内联 script）

- `toggleRagPaper(paperId)` → POST /api/rag/toggle
- `askRagQuestion()` → POST /api/rag/ask，渲染回答
- 不使用 Preact 组件，保持与 workspace 页面其他部分一致的内联 script 风格

---

## 6. 后端改动

### 6.1 新建 `app/routes/api/rag.py`

两个 endpoint：toggle / ask

### 6.2 增强 `app/services/rag_service.py`

- `RagRetrievalService.query()` 新增 `paper_ids` 参数，限定检索范围
- 新增 `_build_rag_context()` 方法：按权重组装索引文本
- `_keyword_fingerprint()` 在 memo 文本上做 word-frequency 加成

### 6.3 StateStore 改动

- `list_workspace_papers()` 新增 `rag_enabled` 过滤参数
- `toggle_rag_paper(paper_id, research_question_id, rag_enabled)` 新方法：
  - 直接 `UPDATE workspace_papers SET rag_enabled = ? WHERE paper_id = ? AND research_question_id = ?`
  - 不走 `upsert_workspace_paper()`（避免触发关系优先级保护逻辑）
  - 若 paper 在该 workspace 中不存在，返回 404

### 6.4 Memo 权重机制

在 `_build_rag_context()` 中处理：

- abstract 和 AI analysis 各出现 1 次
- memo/takeaway 文本 **重复拼接 2 次**（既提高了 keyword fingerprint 中 memo 词汇的 TF 值，又增加了在 AI prompt 中的可见度）

这种简单策略配合 keyword-fingerprint 的 TF 权重，自然实现了 memo 优先。

### 6.4 注册路由

`app/routes/api/__init__.py` 中 import rag 路由

---

## 7. 风险与边界

| 风险 | 处理 |
|------|------|
| 没有任何论文被勾选 | 返回 400 + "请先勾选至少一篇论文" |
| AI 不可用 | 降级为检索片段直出 |
| RAG 检索结果总文本超长 | 截断至 3000 tokens |
| 重复勾选产生冗余 context | RAG 的 cosine similarity 自然排序，低分内容被截断 |
| Memo 为空时检索质量差 | 至少 abstract 始终可用；鼓励用户写 memo |
| 与现有 Agent 面板功能重叠 | RAG Q&A 专注论文内容问答；Agent 保留通用工作流能力 |

---

## 8. 测试清单

### Functional
- `test_rag_toggle_enables_paper`
- `test_rag_toggle_disables_paper`
- `test_rag_toggle_requires_valid_paper_id`
- `test_rag_ask_requires_selected_papers`
- `test_rag_ask_returns_answer_with_ai_provider`
- `test_rag_ask_fallback_without_ai_provider`
- `test_rag_ask_sources_match_selected_papers`

### Integration
- `test_workspace_overview_renders_rag_section`
- `test_workspace_overview_checkbox_toggles_paper`
- `test_rag_qa_template_shows_sources_in_answer`

### RAG correctness
- `test_rag_context_includes_memo_with_higher_weight`
- `test_rag_context_includes_abstract_and_analysis`

---

## 9. 不做的事项

- 不做 PDF 下载 / 解析 / 全文索引
- 不做 real embedding（保持 keyword fingerprint fallback）
- 不做向量数据库（保持 SQLite + struct.pack 存储）
- 不在首版做问答历史持久化（刷新即清空）
- 不新建 Preact 组件（保持内联 script 风格）
- 不修改 Agent 面板逻辑
