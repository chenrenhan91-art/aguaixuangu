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
- 在项目根目录导出一个可直接双击预览的 `A股AI选股工具预览.html`

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

## 部署

仓库根目录已提供：

- `Procfile`
- `render.yaml`

如果部署到 Render：

1. 连接 GitHub 仓库
2. 让 Render 读取仓库根目录的 `render.yaml`
3. 在平台环境变量里填写 `A_SHARE_GEMINI_API_KEY`
4. 部署完成后访问生成的 Web URL

当前部署策略会直接读取仓库中的 `data/processed/daily_candidates_latest.json` 作为初始快照，因此即使云端不执行 AKShare 抓取，也能先正常打开页面。

## 建议的下一步

- 接入真实行情源和新闻源
- 将 demo 数据替换为数据库或 Parquet/DuckDB 查询
- 增加真正的事件抽取和行业映射逻辑
- 扩展 PDF / OCR 交割单解析
- 接入 AI 复盘总结与个性化交易画像
- 完成策略版本管理和实验记录
