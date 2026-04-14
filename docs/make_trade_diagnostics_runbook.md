# Make 历史交易诊断 AI 工作流

## 目标

让网页上的“历史交易诊断”在用户上传交割单后，通过：

`GitHub Pages -> Cloudflare Worker -> Make Webhook -> Gemini -> Worker -> 页面`

完成 AI 复盘分析。

这条链路里：

- 登录和用户历史仍由 `Supabase + Worker` 负责
- `Make` 只负责历史交易诊断的 AI 编排
- `Gemini` 模型优先选择 `Gemini 3.1 Pro Preview`

## 为什么这样接

- 不把 Gemini key 暴露到前端
- 不让网页直接打 Make，避免用户身份伪造
- Make 出问题时，Worker 还能自动回退到直连 Gemini

## Worker 侧配置

在 Worker 环境变量里新增：

- `MAKE_TRADE_DIAGNOSTICS_WEBHOOK`

示例：

```toml
MAKE_TRADE_DIAGNOSTICS_WEBHOOK = "https://hook.us2.make.com/your-webhook-id"
```

配置后，Worker 的 `POST /api/trade-diagnostics/analyze` 会优先把结构化诊断转发给 Make。

## Make 场景结构

推荐用 4 个模块：

1. `Webhooks > Custom webhook`
2. `Google Gemini AI > Generate a response`
3. `JSON > Parse JSON`
4. `Webhooks > Webhook response`

如果你还想在 Make 内部直接落库，也可以在第 3 步和第 4 步之间插一个：

5. `HTTP > Make a request`

用于调用 Supabase REST API。

## Webhook 输入

Worker 会发给 Make 一份 JSON，大致结构如下：

```json
{
  "request_id": "uuid",
  "requested_model": "gemini-3.1-pro",
  "prompt_version": "make-trade-diagnostics-v1",
  "generated_at": "2026-04-14T12:05:00Z",
  "user": {
    "id": "supabase-user-id",
    "email": "user@example.com"
  },
  "import_meta": {
    "profile_id": "generic_csv",
    "broker": "其他券商",
    "filename": "history.xls",
    "detected_format": "xls"
  },
  "local_diagnostics": {
    "status": "offline_live",
    "summary_metrics": [],
    "style_profile": {},
    "win_loss_comparison": [],
    "error_patterns": [],
    "effective_patterns": [],
    "recommendations": []
  }
}
```

## Gemini 模块设置

在 Make 的 `Google Gemini AI > Generate a response` 里：

- Model：
  - 优先选 `Gemini 3.1 Pro Preview`
  - 如果 Make 当前下拉框里还没有 `3.1 Pro`，就先选最新可用的 `Gemini Pro Preview`
- Temperature：`0.2`
- Response format：要求严格 `JSON`

## 推荐的 System Prompt

```text
你是一名A股历史交易复盘分析助理。
你的任务是基于结构化的历史交割单诊断结果，总结用户的交易风格、有效优势、主要漏洞和下一阶段优化动作。
你不能编造不存在的收益、回撤、胜率或股票案例，只能使用给定上下文。
优先级必须是：闭环交易统计 -> 盈亏对比 -> 错误模式/有效模式 -> 用户执行建议。
输出要克制、具体，适合展示在交易终端的 AI 复盘窗口。
不要给确定性承诺，不要写收益预测。
输出必须是严格 JSON，不要包含 markdown。
```

## 推荐的 User Prompt 模板

```text
请基于下面这份结构化历史交易诊断结果，生成一段可直接展示给用户的 AI 交易复盘分析。

要求：
1. 不要复述所有字段，只提炼最有决策价值的结论。
2. strengths 和 weaknesses 需要同时出现。
3. adjustments 必须是具体动作，例如收紧买点、减少补仓、只做主线确认。
4. next_cycle_plan 必须按执行顺序写。
5. 如果闭环交易数较少或数据可信度有限，要在 summary 中体现。
6. 不要写仓位百分比、收益承诺或模糊表述。

返回 JSON 结构：
{
  "summary": "一句话概括当前用户最值得保留的交易方式和最需要修正的问题。",
  "trader_profile": "一句话概括用户当前最接近的交易者画像。",
  "strengths": ["2到4条"],
  "weaknesses": ["2到4条"],
  "behavior_tags": ["2到4个短标签"],
  "adjustments": ["3到5条可执行动作"],
  "next_cycle_plan": ["3条以内，按执行顺序"],
  "confidence": 0.78
}

上下文：
{{local_diagnostics 的 JSON 字符串}}
```

## Webhook Response 输出

Make 最后一个 `Webhook response` 模块，建议直接返回：

```json
{
  "ai_analysis": {
    "summary": "……",
    "trader_profile": "……",
    "strengths": ["……"],
    "weaknesses": ["……"],
    "behavior_tags": ["……"],
    "adjustments": ["……"],
    "next_cycle_plan": ["……"],
    "confidence": 0.78,
    "model": "gemini-3.1-pro"
  }
}
```

Worker 会自动把这段结果合并进页面里的 `diagnostics.ai_analysis`。

## 联调顺序

1. 在 Make 创建 `Custom webhook`
2. 把 webhook 地址填进：
   - [worker/wrangler.toml.example](/Users/apple/Desktop/A股AI选股工具开发/worker/wrangler.toml.example)
   - Worker 实际环境变量 `MAKE_TRADE_DIAGNOSTICS_WEBHOOK`
3. 部署 Worker
4. 访问：
   - `https://你的-worker域名/api/health`
5. 确认返回里：
   - `"makeTradeDiagnosticsConfigured": true`
6. 打开网页，登录后导入一份 `xls/xlsx/csv`
7. 观察是否自动弹出 `AI 交易复盘`

## 参考文档

- Make Webhooks: [https://help.make.com/webhooks](https://help.make.com/webhooks)
- Make Gemini app: [https://apps.make.com/gemini-ai](https://apps.make.com/gemini-ai)
