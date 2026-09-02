# TapTap 社区舆情分析

单机本地部署的社区舆情分析工具。第一阶段支持 TapTap：用户输入 TapTap 社区链接，系统定时抓取帖子，通过兼容 OpenAI API 的本地 AI 模型分析热门话题、玩家情绪、BUG 反馈、玩家建议与游戏内容评价，并通过 Web Dashboard 可视化展示。

> **采集器说明**：当前 TapTap 采集基于 HTTP 适配器（httpx + HTML 解析）。任务 2.3（验证 JS 渲染依赖/引入 Playwright 兜底）已延后处理，待联网环境验证真实页面后再决定。详见 `docs/EXTENSIBILITY.md`。

## 快速开始

### 1. 安装依赖

```bash
py -m pip install -r requirements.txt
```

### 2. 配置 AI 环境变量（必填）

AI 供应商不写死，通过环境变量配置任意兼容 OpenAI API 的端点：

```powershell
$env:OPENAI_BASE_URL = "http://localhost:11434/v1"   # 兼容 OpenAI API 的端点
$env:OPENAI_API_KEY  = "your-key-or-dummy"            # 本地端点可用占位值
$env:OPENAI_MODEL    = "qwen2.5"                       # 调用的模型名
```

### 3. 配置文件（可选）

复制 `config.example.yaml` 为 `config.yaml`，调整端口、限速、调度默认值。AI 配置只走环境变量，不写入 YAML。

### 4. 构建前端

```bash
cd frontend
npm install
npm run build      # 产物输出到 app/dashboard/static/dist
```

### 5. 启动服务

```bash
py -m app serve
```

浏览器访问 `http://127.0.0.1:8000`，注册 TapTap 社区链接即开始定时采集与分析。

## CLI 子命令（调试用）

```bash
# 立即对社区 ID=1 执行一次采集
py -m app collect-now --community 1

# 立即对社区 ID=1 的待分析帖子执行一次分析（不指定 --community 则处理全部）
py -m app analyze-now --community 1
```

## 架构

- `app/core`：配置、数据库（SQLite + WAL）、数据模型、共享基础设施
- `app/collector`：社区注册、采集调度（APScheduler）、TapTap 抓取适配器、限速、去重入库
- `app/analyzer`：兼容 OpenAI API 客户端、五类洞察解析、后台分析消费者、聚合查询
- `app/dashboard`：FastAPI 路由 + 前端静态托管

### 扩展点

- **新增数据源**：实现 `app/collector/adapter.py` 中的 `CommunityAdapter` 接口即可接入 TapTap 以外的社区。
- **替换 AI 后端**：无需改代码，切换环境变量 `OPENAI_BASE_URL`/`OPENAI_API_KEY`/`OPENAI_MODEL` 指向另一个兼容 OpenAI API 的端点即可。

## 测试

```bash
py -m pytest -q
```

## 环境变量

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | 是 | 兼容 OpenAI API 的端点地址 |
| `OPENAI_API_KEY`  | 是 | API Key（本地端点可用占位值） |
| `OPENAI_MODEL`    | 是 | 调用的模型名 |

## 非目标

- 第一阶段不支持 TapTap 以外平台（架构已预留扩展点）
- 不实现钉钉日报（DingTalk daily report）
- 不支持多用户鉴权与云端部署

## 平台采集风控与合规

本系统在多平台采集时严格遵守合规边界：

- **不绕过验证码**：检测到验证码/风控页面即停止该平台采集
- **不破解风控**：不破解任何平台的安全机制
- **不伪造身份**：不伪造用户身份、设备指纹或 Cookie
- **不无限重试**：平台明确拒绝（403/412/429/验证码）时立即停止，仅对网络错误做有限次重试
- **单平台隔离**：单个平台风控不影响其他平台与整个舆情系统运行

风控状态识别覆盖：HTTP 403 / 412 / 429 / 验证码页面 / 登录失效（401）/ 网络超时。各平台采集状态可在 Dashboard「采集状态」页面查看（正常 / 采集中 / 限流 / 风控阻断 / 登录失效 / 网络错误）。

若某平台被风控阻断，建议检查：平台授权是否有效、是否需要使用官方 API、登录状态是否过期、或采用其他合规的数据获取方式。

## AI 分析与采集解耦

- 采集入库的帖子自动进入待分析队列（PENDING），由后台 AI 消费者拾取分析
- AI 分析失败不阻塞采集任务，两者为独立链路
- AI 服务不可用时帖子仍正常入库，恢复后可继续处理 PENDING 帖子
- AI 分析失败记录原因、重试次数与状态（retryable / abandoned），达到上限标记 failed
- AI 原始分析结果（AnalysisResult）与人工评估标注（Review）独立存储，人工评估不覆盖 AI 原始结果
