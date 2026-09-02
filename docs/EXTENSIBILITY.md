# 扩展点说明

本项目设计了两处主要扩展点，便于后续替换数据源或 AI 后端，而无需改动核心流程。

## 1. 社区抓取适配器 `CommunityAdapter`

- 接口定义：`app/collector/adapter.py` 中的 `CommunityAdapter` 抽象类。
- 现有实现：`app/collector/taptap_adapter.py`（TapTap 网页抓取，基于 httpx + HTML 解析）。

### 关于 JS 渲染（2.3 延后说明）

- **当前采集器基于 HTTP 适配器**（`TapTapAdapter`），使用 `httpx` 直接抓取页面 HTML 并解析。
- **任务 2.3 已延后处理（DEFERRED）**：尚未在本地联网环境验证真实 TapTap 社区列表是否依赖 JS 渲染。
- **后续计划**：待联网环境验证后，若 HTTP 无法获取完整帖子列表，再引入 Playwright 作为兜底适配器实现（通过 `CommunityAdapter` 接口隔离，无需改动调用方与核心采集逻辑）。
- 在此之前不引入 Playwright 依赖，保留现有 HTTP 适配器实现不变。

### 新增数据源步骤
  1. 新建 `app/collector/<platform>_adapter.py`，实现 `CommunityAdapter` 的全部抽象方法：
     - `parse_community_id(raw_url)`：把原始链接解析为稳定社区标识。
     - `fetch_post_list(community_id, limit)`：抓取帖子列表。
     - `fetch_post_detail(post_ref)`：抓取单帖详情，返回 `FetchedPost`。
     - `is_anti_crawl_response(status_code, body_sample)`：反爬拦截判定。
  2. 在调用处（如 `app/dashboard/server.py` 的 `_collect_community` 与 `app/dashboard/routes.py` 的注册接口）将 `TapTapAdapter` 替换为你的实现，或引入工厂按平台分发。
  3. 其余采集调度、去重入库、collection_runs 记录、限速、重试逻辑无需改动。

## 2. AI 分析后端 `SinglePostAnalyzer`

- 当前实现：`app/analyzer/analyzer.py` 的 `SinglePostAnalyzer`，内部使用 OpenAI 兼容客户端。
- 切换后端：无需改代码。只需修改环境变量：
  - `OPENAI_BASE_URL`：指向新的兼容 OpenAI API 的端点。
  - `OPENAI_API_KEY`：对应 API Key。
  - `OPENAI_MODEL`：对应模型名。
- 替换为非 OpenAI 兼容后端：实现一个返回 `AnalysisPayload` 的分析器，并在 `app/dashboard/server.py` 的 `_analyzer_factory` 中替换 `SinglePostAnalyzer` 构造即可。
- 五类洞察的结构化契约由 `app/analyzer/parser.py` 的 `parse_analysis_json` 与 `app/analyzer/schema.json` 定义，保持契约不变即可。
