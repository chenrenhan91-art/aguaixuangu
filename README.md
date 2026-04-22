# A股 AI 选股与历史交易诊断

这个项目已经收口成一套“**纯静态前端 + GitHub Actions 日更 + Supabase 登录历史 + Make 调 Gemini**”的最小主流程，核心只保留两个页面：

- `AI选股`
- `历史交易诊断`

## 当前正式架构

`GitHub Actions 定时更新快照 -> GitHub Pages 静态页面 -> Supabase 登录/历史 -> Make.com 调 Gemini`

也就是说：

- 每日两次更新仍由 GitHub Actions 负责
- 页面本身是静态页，不依赖你自己部署服务器
- 用户注册登录与个人历史交给 Supabase
- 个股 AI 分析和交易诊断 AI 结论交给 Make.com webhook，再由 Make 调用 Gemini

## 两个核心功能

### 1. AI选股

- GitHub Actions 在北京时间 `11:35`、`15:05` 尝试刷新
- 先检查是否是 A 股交易日
- 使用免费数据源抓取行业、个股、事件数据
- 按不同策略模式筛选对应最适配的 5 只股票
- 页面读取 `data/processed/daily_candidates_latest.json`
- 支持分析：
  - 今日候选股
  - 用户手动输入的股票代码

### 2. 历史交易诊断

- 页面支持 `csv / xls / xlsx`
- 浏览器本地解析交割单
- 本地先生成结构化统计：
  - 交易风格画像
  - 胜率 / 盈亏比 / 持仓周期
  - 赚钱模式 / 亏钱漏洞
- 再把结构化诊断结果发给 Make.com webhook
- Make 调用 Gemini 返回 AI 总结与优化建议
- 用户登录后，诊断结果保存到 Supabase

## 项目结构

- `index.html`: 当前主页面，已经改成静态页直连 Supabase + Make
- `data_pipeline/`: 数据抓取、筛选、快照生成
- `data/processed/`: 每日快照 JSON
- `supabase/schema.sql`: 用户历史表与 RLS 策略
- `.github/workflows/refresh_snapshot.yml`: 每日两次自动刷新快照
- `requirements-pipeline.txt`: 选股流水线所需的最小 Python 依赖
- `docs/github_pages_supabase_make_runbook.md`: 当前正式部署说明

## 本地最少命令

```bash
make install
make check-trade-day
make snapshot
```

## 你真正需要配置的只有 3 个地方

### 1. GitHub Actions

文件：

- `.github/workflows/refresh_snapshot.yml`

作用：

- 工作日北京时间 `11:35`
- 工作日北京时间 `15:05`
- 更新 `data/processed/*.json`

### 2. Supabase

你需要执行：

- `supabase/schema.sql`

作用：

- 建表 `trade_diagnostics_history`
- 建表 `analysis_history`
- 启用 RLS
- 允许用户只读写自己的历史记录

### 3. 前端运行时配置

直接在 `index.html` 顶部的 `window.APP_RUNTIME` 中填写：

```js
window.APP_RUNTIME = {
  snapshotUrl: "./data/processed/daily_candidates_latest.json",
  makeExecutionAnalysisWebhook: "你的 Make 个股分析 webhook",
  makeTradeDiagnosticsWebhook: "你的 Make 交易诊断 webhook",
  supabaseUrl: "你的 Supabase URL",
  supabaseAnonKey: "你的 Supabase anon key",
  geminiModel: "gemini-3-pro-preview",
  schedules: ["11:35", "15:05"],
};
```

## 当前说明

- GitHub Actions 只负责更新 `daily_candidates_latest.json`
- GitHub Pages 只负责展示静态页
- Supabase 只负责注册登录和用户历史
- Make webhook 只负责调用 Gemini 并返回结构化结果
- 仓库已经移除了旧的 `backend / worker / demo render` 主链依赖，避免后续维护时再被旧实现干扰
