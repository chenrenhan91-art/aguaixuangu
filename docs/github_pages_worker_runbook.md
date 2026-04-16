# GitHub Pages + Supabase + Make 上线方案

当前项目已经不再把 `Cloudflare Worker` 作为正式主流程依赖。

新的线上链路是：

`GitHub Pages 静态前端 -> Supabase 登录与历史 -> Make webhook -> Gemini`

## 目标

- `GitHub Pages` 承载唯一页面 `index.html`
- `GitHub Actions` 在北京时间 `12:05` 和 `15:05` 刷新选股快照
- `Supabase Auth` 负责注册登录
- `Supabase` 负责保存用户自己的个股分析与交易诊断历史
- `Make.com` 负责调用 `Gemini`

## 最终链路

### A. 选股更新

1. GitHub Actions 定时触发
2. 执行 Python 数据流水线
3. 更新 `data/processed/daily_candidates_latest.json`
4. GitHub Pages 页面自动读取最新 JSON

### B. 个股 AI 执行分析

1. 用户点击候选股，或手动输入股票代码
2. 前端把股票上下文发给 `Make webhook`
3. Make 调 `Gemini`
4. Make 返回结构化分析 JSON
5. 前端展示分析结果
6. 若用户已登录，则结果保存到 `analysis_history`

### C. 历史交易诊断

1. 用户登录
2. 用户上传 `xls / xlsx / csv`
3. 浏览器本地解析交割单并生成结构化诊断
4. 前端把结构化诊断发给 `Make webhook`
5. Make 调 `Gemini`
6. 前端把完整结果写入 `trade_diagnostics_history`

## 你需要配置的内容

### 1. GitHub Actions

仓库已提供：

- `.github/workflows/refresh_snapshot.yml`

当前调度：

- 北京时间 `12:05`
- 北京时间 `15:05`
- 非交易日自动跳过

### 2. Supabase

需要执行：

- `supabase/schema.sql`

作用：

- 创建 `trade_diagnostics_history`
- 创建 `analysis_history`
- 启用行级权限
- 允许登录用户只读写自己的历史数据

### 3. 前端运行时配置

在 `index.html` 里填写：

- `makeExecutionAnalysisWebhook`
- `makeTradeDiagnosticsWebhook`
- `supabaseUrl`
- `supabaseAnonKey`
- `geminiModel`

## 说明

- 这个方案不需要你部署自己的后端服务器
- 如果浏览器直连 Make webhook 遇到 CORS 限制，再考虑补一层极轻量代理
- 在当前阶段，`backend/` 和 `worker/` 目录都不是正式主流程
