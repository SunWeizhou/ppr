# arXiv Recommender 系统审查与优化计划

经过对项目的全面审查（包括自动依赖检查、跨文件函数调用验证、代码结构扫描以及完整的UI视觉测试），我发现了系统中存在一系列关键的功能和UI问题，特别是前端模板与底层重构脱节导致的大量异常。

下面我整理了你需要交给其他Agent执行的**优化计划（Optimization Plan）**。这个计划非常详细，你可以直接复制这些任务分配下去。

---

## 一、高优先级问题 (P0: 运行时错误与功能断裂)

这些问题会导致用户在点击特定按钮时系统完全没反应（控制台报错）。由于最近的重构改变了函数名或导出方式，许多 HTML 模板中绑定的 `onclick` 事件已经失效。

### 1. 修复核心功能按钮失效 (缺失的 JS 全局函数)
**问题:** `today.html` 和 `reading.html` 中调用的核心纸张操作函数在 `window` 对象上未定义或丢失。
**需要执行的操作:**
*   **修复 `queuePaper` 缺失:** 模板中到处都在调用 `queuePaper(paperId, '...')`（在 `today.html`, `reading.html`, `favorites_research.html` 和 `command_palette.js` 中），但在重构时 `paper_actions.js` 中改名为 `queuePaperStatus`。
    *   **解决:** 在 `paper_actions.js` 末尾的 `Object.assign(window, {...})` 中增加 `queuePaper: queuePaperStatus` 作为别名，以兼容旧版模板的调用。
*   **修复 `submitPaperFeedback` 缺失:** `today.html` 的 "Pass remaining" 和卡片操作中调用了 `submitPaperFeedback(paperId, 'dislike')`。这原本存在于旧版逻辑中，但在重构后的 `inbox.js` 中名字变成了 `submitSelectedFeedback`。
    *   **解决:** 在 `inbox.js` 导出的 `submitSelectedFeedback` 只支持操作*当前选中*的论文。需要修改 `today.html` 和 `command_palette.js`，让它们调用正确的批量 API (如 `/api/feedback/batch`)，或者在 `inbox.js` 中实现一个能接收明确 `paperId` 的 `submitPaperFeedback` 并暴露到 window。

### 2. 修复 Watch 页面 (订阅管理) 全面瘫痪
**问题:** `watch.html` 页面依赖了 6 个 JS 函数，但在 `subscriptions.js` 没有任何匹配。
**需要执行的操作:**
*   **修正未定义的函数绑定:** `watch.html` 绑定的 `runAllSubscriptions()`, `runSubscription()`, `editSubscription()`, `createQuerySubscription()`, `createAuthorSubscription()`, `createVenueSubscription()` 都是 undefined。
*   **解决:** 
    *   把 `watch.html` 里的 `createQuerySubscription` 改成调用 `subscriptions.js` 里的 `openQuerySubscriptionModal()`。
    *   把 `createAuthorSubscription` 改成调用 `openAuthorSubscriptionModal()`。
    *   将缺少的刷新 (`runSubscription`) 和修改逻辑补充到 `subscriptions.js` 或对应模板的 script 标签中（直接对接后端的 `POST /api/subscriptions/run` API 等）。

### 3. 补全缺失的 UI 组件宏与 CSS 类
**问题:** UI 设计中的某些类和组件未在代码中找到。
**需要执行的操作:**
*   **丢失的按钮样式:** `btn-sage` 和 `btn-secondary` 按钮类被使用（分别在 `today.html` 和 `settings_research.html`）但并未在任何 CSS 文件中定义。在 `components.css` 中补全这两个类（例如为 `.btn-sage` 添加莫兰迪绿色，为 `.btn-secondary` 添加灰色轮廓）。
*   **丢失的 JS 函数:** `base_research.html` 尝试在移动端点击背景蒙层时调用 `closeMobileDetail()`，但这并未在 JS 中定义。在 `app.js` 或直接在行内补充 `closeMobileDetail` 函数以移除 `mobile-detail-open` 类。

---

## 二、中优先级问题 (P1: 样式、视觉和体验)

在自动化浏览器测试中（尤其是从你之前的截图和深色模式观察），发现了深色模式重写不完整和布局的问题。

### 1. 修复深色模式(Dark Mode)的视觉缺陷
**问题:** 虽然我们之前处理了硬编码的 rgba 颜色，但深色模式依然存在瑕疵，且某些弹窗的默认文字颜色不可见。
**需要执行的操作:**
*   **输入框在深色模式下的对比度:** 确保 `settings_research.html` 里的 `<input>` 和 `<select>` 在深色模式下具有正常的白/灰色文字，而不是受全局 ink 控制导致的模糊。
*   **阅读界面(Reading)的高亮颜色:** 阅读界面的评分胶囊（Score chip）和状态胶囊目前的颜色对暗模式适配不佳，在 `components.css` 为它们添加 `[data-theme="dark"]` 后备样式。

### 2. API 异常处理和空状态 (Empty State) 优化
**问题:** 当系统没有推荐或者后台报错时，UI 处理很生硬。
**需要执行的操作:**
*   **改进 Inbox 空状态:** `inbox.js` 依赖 `skeletonLoader`。但是如果在网络较慢时，应该确保 skeleton 一直显示直到 API 返回。
*   **Python Flask Route 容错:** `api/feedback.py` 中的 `/api/refresh` 的强制刷新目前只有非常简单的 `try/except`。需要确保如果 background thread (Daemon) 卡死，前端页面不会陷入无尽的 "刷新中"。

---

## 三、低优先级问题 (P2: 代码清理与依赖优化)

### 1. 清理冗余依赖项
**问题:** `requirements.txt` 列出了很多我们在代码中其实没有使用的重型依赖。
**需要执行的操作:**
*   你现在的代码只真正 import 了 `flask`, `flask_cors`, `defusedxml` 以及内置库。
*   `requirements.txt` 里存在的 `sentence-transformers`, `torch`, `transformers` 占据了巨大的体积（几个 GB），但实际上在重构到 V2 排行榜（使用外部 AI provider 例如 DeepSeek）之后，本地似乎不需要跑重型 transformer 了。
*   **解决:** 检查如果你的系统完全剥离了本地大模型，请将 `torch` 和 `transformers` 从 `requirements.txt` 中移除，这会极大加速后续你使用其他 agent 修复 Python 虚拟环境的成功率。

### 2. 完善路径和环境变量
**问题:** 测试系统时发现 `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))` 被广泛使用。
**需要执行的操作:**
*   彻底梳理 `app_paths.py`，将所有的绝对路径 (`/Users/sunweizhou/...`) 强制替换为相对于 `PROJECT_ROOT` 的动态解析路径，避免系统迁移时崩溃。

---

## 接下来你可以直接发给其他 Agent 的 Prompt（执行指令）：

你可以复制以下内容发送给负责具体编码的 Agent 进行第一阶段的抢修：

> **Task: Fix Broken JS Function References and Templates in arXiv Recommender**
> 
> Please fix the following critical front-end disconnects in the project:
> 
> 1. **`queuePaper` is missing:** In `static/js/paper_actions.js`, the function is named `queuePaperStatus`. Please add `queuePaper: queuePaperStatus` to the `Object.assign(window, {...})` export at the end of the file.
> 2. **`submitPaperFeedback` is missing:** Templates like `today.html` call `submitPaperFeedback(paperId, 'dislike')`, but it doesn't exist. Please implement a global function `submitPaperFeedback(paperId, action)` in `static/js/inbox.js` that makes a POST request to `/api/feedback` with the paper_id and action, or map it to the existing batch function if appropriate.
> 3. **Fix `watch.html` function calls:** Open `templates/watch.html` and `static/js/subscriptions.js`. The template calls `createQuerySubscription()`, `createAuthorSubscription()`, and `createVenueSubscription()`. Change the template to call the correct exported functions: `openQuerySubscriptionModal()`, `openAuthorSubscriptionModal()`, etc.
> 4. **Add missing CSS classes:** In `static/css/components.css`, add styles for `.btn-sage` (a sage green button) and `.btn-secondary`. 
> 5. **Fix mobile detail toggle:** Implement a global function `closeMobileDetail()` in `app.js` that removes the class `mobile-detail-open` from `document.body`.
