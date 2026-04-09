# GitHub Pages + Worker 上线方案

## 目标

- `GitHub Pages` 承载唯一页面 [index.html](/Users/apple/Desktop/A股AI选股工具开发/index.html)
- `GitHub Actions` 在北京时间 `12:05` 和 `15:05` 自动刷新选股快照
- `Cloudflare Worker` 直连 `Gemini`
- `Supabase Auth` 负责登录
- `Supabase` 保存每个用户自己的交易诊断历史

## 最终链路

### A. 选股更新

1. GitHub Actions 定时触发
2. 执行 Python 数据流水线
3. 更新：
   - [index.html](/Users/apple/Desktop/A股AI选股工具开发/index.html)
   - [data/processed/daily_candidates_latest.json](/Users/apple/Desktop/A股AI选股工具开发/data/processed/daily_candidates_latest.json)
4. GitHub Pages 自动提供最新页面

### B. 个股 AI 执行分析

1. 用户点击页面中的 `AI 交易执行分析`
2. 前端把当前个股 detail 发给 Worker
3. Worker 调 Gemini
4. Worker 返回结构化分析 JSON
5. 前端弹窗展示

### C. 历史交易诊断

1. 用户登录
2. 用户上传 `xls / xlsx / csv`
3. 浏览器本地解析成交记录
4. 前端把本地结构化诊断结果发给 Worker
5. Worker 调 Gemini
6. Worker 把结果写入 Supabase
7. 用户再次访问时，前端自动读取自己的最近诊断历史

## 你需要配置的 4 个地方

### 1. GitHub Secrets

在仓库 Secrets 里新增：

- `A_SHARE_GEMINI_API_KEY`

作用：

- 供 [refresh_snapshot.yml](/Users/apple/Desktop/A股AI选股工具开发/.github/workflows/refresh_snapshot.yml) 在定时更新时使用

### 2. Cloudflare Worker

仓库里已有：

- [worker/index.js](/Users/apple/Desktop/A股AI选股工具开发/worker/index.js)
- [worker/wrangler.toml.example](/Users/apple/Desktop/A股AI选股工具开发/worker/wrangler.toml.example)

你需要配置：

- `APP_ORIGIN`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- Secret: `GEMINI_API_KEY`
- Secret: `SUPABASE_SERVICE_ROLE_KEY`

### 3. Supabase

需要执行：

- [supabase/schema.sql](/Users/apple/Desktop/A股AI选股工具开发/supabase/schema.sql)

作用：

- 创建 `trade_diagnostics_history`
- 建立索引
- 启用 RLS

### 4. 前端运行时配置

在 [index.html](/Users/apple/Desktop/A股AI选股工具开发/index.html) 里的 `APP_RUNTIME` 填：

- `aiProxyBaseUrl`
- `supabaseUrl`
- `supabaseAnonKey`

## Worker 提供的接口

### `GET /api/health`

返回：

```json
{
  "status": "ok",
  "provider": "cloudflare-worker",
  "geminiConfigured": true,
  "supabaseConfigured": true,
  "model": "gemini-3-pro-preview"
}
```

### `POST /api/trade-diagnostics/analyze`

前端发送：

```json
{
  "profileId": "generic_csv",
  "broker": "其他券商",
  "filename": "history.xls",
  "detectedFormat": "xlsx",
  "trades": [],
  "localDiagnostics": {}
}
```

返回：

```json
{
  "diagnostics": {
    "...": "完整诊断",
    "ai_analysis": {
      "status": "ai_live",
      "model": "gemini-3-pro-preview",
      "summary": "",
      "trader_profile": "",
      "strengths": [],
      "weaknesses": [],
      "behavior_tags": [],
      "adjustments": [],
      "next_cycle_plan": []
    }
  }
}
```

### `POST /api/trade-diagnostics/history`

说明：

- 需要登录后自动带 `Authorization Bearer`
- Worker 会验证当前 Supabase session

返回：

```json
{
  "diagnostics": {
    "...": "最近一次诊断",
    "recent_batches": []
  }
}
```

### `POST /api/stocks/execution-analysis`

前端发送：

```json
{
  "symbol": "301396",
  "mode_id": "balanced",
  "signal": {},
  "detail": {},
  "trade_date": "2026-04-09"
}
```

返回：

```json
{
  "analysis": {
    "status": "ai_live",
    "model": "gemini-3-pro-preview",
    "summary": "",
    "stance": "跟踪",
    "setup_quality": "B",
    "key_signal": "",
    "highlights": [],
    "trigger_points": [],
    "invalidation_points": [],
    "execution_plan": [],
    "next_step": "",
    "source": "worker-gemini"
  }
}
```

## GitHub Actions 定时任务

仓库已提供：

- [.github/workflows/refresh_snapshot.yml](/Users/apple/Desktop/A股AI选股工具开发/.github/workflows/refresh_snapshot.yml)

当前调度：

- 北京时间 `12:05`
- 北京时间 `15:05`

## 最小验收顺序

1. 执行 Supabase SQL
2. 部署 Worker
3. 打开：

`https://你的-worker域名/api/health`

4. 在 [index.html](/Users/apple/Desktop/A股AI选股工具开发/index.html) 中填：
   - `aiProxyBaseUrl`
   - `supabaseUrl`
   - `supabaseAnonKey`
5. 部署 GitHub Pages
6. 注册一个测试账号
7. 导入一份 `xls/xlsx/csv`
8. 确认：
   - 自动弹出 `AI 交易复盘`
   - 刷新页面后仍能看到最近历史
   - 个股 `AI 交易执行分析` 弹窗显示 `gemini-3-pro-preview`
