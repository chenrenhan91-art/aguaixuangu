# Make + Gemini 个股交易分析接入说明

这套说明对应页面里的“AI 交易执行分析”功能。

当前实现已经改成：

- 用户在前端输入股票代码
- 前端按输入代码构造分析请求
- 不再依赖“当前选中的候选股”作为唯一分析对象
- 若输入代码命中本地快照，会把该股票的快照数据一并传给 Make
- 若未命中本地快照，仍会把股票代码、市场环境和模式偏好发给 Make

## 新的前端入参逻辑

前端现在发送的是“股票代码驱动”的 payload，核心字段包括：

- `analysis_type`
- `requested_symbol`
- `stock_code`
- `selected_mode_id`
- `matched_snapshot`
- `market_snapshot`
- `analysis_context_json`
- `analysis_prompt`

样例见：

- [sample_payload.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/sample_payload.json)

## 推荐场景结构

推荐最小同步链路：

1. `Webhooks > Custom webhook`
2. `HTTP > Make a request`
3. `Webhooks > Webhook response`

如果你希望“任意股票代码”都尽量有更完整的数据，可以在第 2 步前额外插入一个数据抓取步骤：

1. `Webhooks > Custom webhook`
2. `HTTP / 数据模块 > 拉取个股行情 / 新闻 / 技术指标`
3. `HTTP > Make a request`
4. `Webhooks > Webhook response`

前端本身不要求这一步，但如果输入代码没有命中本地快照，是否能给出更细的价格级分析，就取决于你是否在 Make 里补了外部数据。

## 第 1 步：创建 webhook

1. 在 Make 新建 Scenario。
2. 添加 `Webhooks > Custom webhook`。
3. 复制 webhook URL。
4. 点击 `Run once`，让它等待样例请求。

然后在仓库根目录运行：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL" \
  "./docs/make_execution_analysis/sample_payload.json"
```

## 第 2 步：HTTP 模块调用 Gemini

在 Scenario 中添加 `HTTP > Make a request`。

推荐配置：

- Method: `POST`
- URL:

```text
https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent
```

- Headers:

```text
x-goog-api-key: 你的 Gemini API Key
Content-Type: application/json
```

- Body type: `Raw`
- Content type: `JSON (application/json)`

Body 示例：

```json
{
  "contents": [
    {
      "parts": [
        {
          "text": "{{1.analysis_prompt}}"
        }
      ]
    }
  ],
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseJsonSchema": {
      "type": "object",
      "properties": {
        "summary": { "type": "string" },
        "technical_judgment": { "type": "string" },
        "stop_loss_price": { "type": "number" },
        "take_profit_price_1": { "type": "number" },
        "take_profit_price_2": { "type": "number" },
        "invalidation_points": { "type": "array", "items": { "type": "string" } },
        "action_note": { "type": "string" },
        "confidence": { "type": "number" },
        "model": { "type": "string" },
        "generated_at": { "type": "string" }
      },
      "required": [
        "summary",
        "technical_judgment",
        "stop_loss_price",
        "take_profit_price_1",
        "take_profit_price_2",
        "invalidation_points",
        "action_note",
        "confidence",
        "model",
        "generated_at"
      ]
    }
  },
  "systemInstruction": {
    "parts": [
      {
        "text": "你是 A 股个股交易分析助手。请只返回 JSON，不要返回 Markdown 或代码块。如果缺少可靠价格或技术数据，不要编造，把价格字段返回 0，并在 summary 和 technical_judgment 里明确说明当前只能给方向性判断。"
      }
    ]
  }
}
```

说明：

- `{{1.analysis_prompt}}` 由前端按输入股票代码动态生成
- 当前 prompt 已经约束“不要给仓位比例”“缺数据时不要编造价格”
- 如果输入代码命中前端快照，prompt 会带上该股票已有的结构化上下文
- 如果没命中，只会带股票代码和市场环境摘要

## 第 3 步：Webhook response 模块

最后添加 `Webhooks > Webhook response`。

推荐配置：

- `Status`: `200`
- `Body`: 返回 HTTP 模块的响应体原文
- `Content-Type`: `application/json`

如果你临时排障，可以直接把 `Body` 改成固定 JSON，先验证“前端 <-> Make 通路”：

```json
{
  "summary": "Make fixed response ok",
  "technical_judgment": "测试返回，当前只验证前端是否能正常接收并展示 JSON。",
  "stop_loss_price": 0,
  "take_profit_price_1": 0,
  "take_profit_price_2": 0,
  "invalidation_points": ["test"],
  "action_note": "这是固定测试响应。",
  "confidence": 0.9,
  "model": "make-test",
  "generated_at": "2026-04-18T22:02:00+08:00"
}
```

## 第 4 步：前端配置 webhook

在 [index.html](/Users/apple/Desktop/aguaixuangu-main/index.html) 的 `APP_RUNTIME` 中填写：

```js
makeExecutionAnalysisWebhook: "你的 Make webhook URL",
```

兼容旧字段：

```js
MAKE_COM_AI_WEBHOOK_URL: "你的 Make webhook URL",
```

## 第 5 步：验证

先运行：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL"
```

然后打开页面，在“个股总览”右上角：

1. 输入 6 位股票代码
2. 点击“AI 交易执行分析”

前端现在会：

- 只按输入股票代码发起请求
- 在弹窗里显示本次分析的目标股票代码
- 如果 Make 返回异常，会在“调用诊断”里显示 HTTP 状态、返回片段和等待时长

## 当前设计的关键差异

旧逻辑：

- 基于 `state.currentSymbol`
- 直接取当前候选股的 `detail/signal`
- 只适合分析候选池里当前选中的股票

新逻辑：

- 基于用户输入的 `stock_code`
- 先按输入代码尝试命中本地快照
- 命中则附带本地结构化上下文
- 未命中也照样把股票代码和市场环境发给 Make
- 前端分析对象不再依赖当前候选池选中项

## 文件清单

- [README.md](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/README.md)
- [response_schema.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/response_schema.json)
- [sample_payload.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/sample_payload.json)
- [system_prompt.md](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/system_prompt.md)
- [verify_make_execution_webhook.sh](/Users/apple/Desktop/aguaixuangu-main/scripts/verify_make_execution_webhook.sh)
