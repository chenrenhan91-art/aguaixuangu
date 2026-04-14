# A股 AI 选股工具

这是基于 `V2` 方案收缩后的项目骨架，目标是优先交付一个可直接在浏览器中查看的 AI 选股工具，并逐步扩展成“AI 选股 + 历史交易诊断”的研究工作台。

## 目录结构

- `backend/`: FastAPI 后端接口和服务层
- `data_pipeline/`: 数据抓取、清洗、事件抽取和快照导出任务
- `docs/`: 架构说明
- `data/`: 原始数据、处理数据和交易诊断存储

## 快速启动

### 1. 启动后端

```bash
make backend-install
make backend-dev
```

后端默认地址：

- `http://localhost:8000/`
- 文档：`http://localhost:8000/docs`

打开根路径后即可直接看到 HTML 仪表盘，无需额外启动前端。

### 1.1 配置 Gemini

复制 `.env.example` 为 `.env`，至少补上：

```bash
A_SHARE_GEMINI_API_KEY=你的_Gemini_API_Key
A_SHARE_GEMINI_MODEL=gemini-3-pro-preview
```

当前已接入的 AI 能力：

- 市场情绪分析
- 个股 AI 交易执行分析
- 历史交易诊断 AI 复盘

### 2. 运行数据管道示例任务

```bash
make pipeline-refresh
make pipeline-candidates
```

其中 `make pipeline-candidates` 会做三件事：

- 拉取 AKShare 行业和个股真实数据
- 基于新闻标题和摘要做事件抽取
- 在项目根目录导出唯一的离线页面 `index.html`

## 当前骨架包含的能力

- FastAPI 接口骨架
- 市场状态、行业轮动、候选池和个股详情接口
- 后端直出的 HTML 仪表盘页面
- 基于 AKShare 的真实行业/个股数据抓取链路
- 基于东财新闻的轻量事件抽取与候选池生成
- 历史交易诊断工作区
- CSV / XLSX 交割单导入接口和 SQLite 存储
- 交易风格画像、盈亏对比、错误模式和优化建议输出
- 数据管道适配器和数据质量校验
- 基础测试样例

## 历史交易诊断模块

- 页面入口：根路径首页右上方工作区切换
- API：
  - `GET /api/trade-diagnostics/profiles`
  - `POST /api/trade-diagnostics/import`
  - `GET /api/trade-diagnostics/summary`
  - `POST /api/trade-diagnostics/ai-analysis`
  - `GET /api/trade-diagnostics/schema`
- 设计说明：`docs/trade_diagnostics_module.md`

## GitHub Pages + Worker 部署

当前推荐的 ToC 部署方式是：

- `GitHub Pages` 承载静态前端
- `GitHub Actions` 在北京时间 `12:05` 和 `15:05` 尝试刷新选股页，并在运行前自动校验是否为 A 股交易日
- `Cloudflare Worker` 作为轻量后端，直连 `Gemini`
- `Supabase Auth` 负责登录与诊断历史

仓库已提供：

- [.github/workflows/refresh_snapshot.yml](/Users/apple/Desktop/A股AI选股工具开发/.github/workflows/refresh_snapshot.yml)
- [worker/index.js](/Users/apple/Desktop/A股AI选股工具开发/worker/index.js)
- [worker/wrangler.toml.example](/Users/apple/Desktop/A股AI选股工具开发/worker/wrangler.toml.example)
- [supabase/schema.sql](/Users/apple/Desktop/A股AI选股工具开发/supabase/schema.sql)
- [docs/github_pages_worker_runbook.md](/Users/apple/Desktop/A股AI选股工具开发/docs/github_pages_worker_runbook.md)

部署前你需要配置：

1. GitHub 仓库 Secret：
   - `A_SHARE_GEMINI_API_KEY`
2. Cloudflare Worker：
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - Secret: `GEMINI_API_KEY`
   - Secret: `SUPABASE_SERVICE_ROLE_KEY`
3. `index.html` 中的运行时配置：
   - `APP_RUNTIME.aiProxyBaseUrl`
   - `APP_RUNTIME.backendApiBaseUrl`（本地联调可填 `http://localhost:8000/api`）
   - `APP_RUNTIME.supabaseUrl`
   - `APP_RUNTIME.supabaseAnonKey`

未完成这些配置前，页面仍会保留本地回退模式：

- 选股页读取仓库里的最新静态快照
- 交割单仍可在浏览器内本地解析
- AI 诊断会回退为本地结构化分析

## 建议的下一步

- 接入真实行情源和新闻源
- 将 demo 数据替换为数据库或 Parquet/DuckDB 查询
- 增加真正的事件抽取和行业映射逻辑
- 扩展 PDF / OCR 交割单解析
- 接入 AI 复盘总结与个性化交易画像
- 完成策略版本管理和实验记录
