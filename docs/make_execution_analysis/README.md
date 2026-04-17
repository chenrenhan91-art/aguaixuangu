# Make + Gemini 个股执行分析接入说明

这套说明对应页面里的“AI 交易执行分析”按钮。

当前仓库已经做好的部分：

- 前端会优先读取 `makeExecutionAnalysisWebhook`，同时兼容旧字段 `MAKE_COM_AI_WEBHOOK_URL`
- 前端会把 `analysis_prompt`、`analysis_context_json` 和结构化股票上下文一起 POST 到 Make webhook
- 前端既能解析 Make 直接返回的结构化 JSON，也能解析“原样转发的 Gemini REST 响应”
- 仓库内置了 webhook 自检脚本：`scripts/verify_make_execution_webhook.sh`

## 当前已确认的问题

仓库原先硬编码的 Make webhook 已失效，返回：

`410 There is no scenario listening for this webhook.`

这通常意味着 webhook 已经不再连接任何活动场景，或者对应场景已被停用太久。

## 目标场景结构

推荐用最小可运行链路：

1. `Webhooks > Custom webhook`
2. `HTTP > Make a request`
3. `Webhooks > Webhook response`

这样前端点击按钮后，可以同步拿到 Gemini 结果，不需要轮询。

## 第 1 步：创建 Custom webhook

1. 登录 Make.com。
2. 新建一个 Scenario。
3. 添加模块 `Webhooks > Custom webhook`。
4. 名称建议填：`AI Trading Execution Analysis`。
5. 复制生成的 webhook URL。
6. 先不要急着开场景，先点击 `Run once`，让它等待样例请求。

## 第 2 步：让 webhook 识别输入结构

在本仓库根目录运行：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL" \
  "./docs/make_execution_analysis/sample_payload.json"
```

第一次运行时，如果你的 Scenario 还停在 `Run once` 状态，Make 会收到样例并识别 webhook 数据结构。

如果你不想立即验证，也可以用任意 `curl` 或 Postman 把 `sample_payload.json` POST 到 webhook。

## 第 3 步：HTTP 模块调用 Gemini

在 Scenario 中添加 `HTTP > Make a request` 模块。

推荐模型：

- 低延迟优先：`gemini-3-flash-preview`
- 更强推理：`gemini-3.1-pro-preview`

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

Body 可以直接使用下面这个模板：

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
        "text": "你是 A 股交易执行分析助手。请只返回 JSON，不要返回 Markdown 或代码块。核心输出技术面判断、止损位、两档止盈位和失效条件，不要给明确仓位比例。"
      }
    ]
  }
}
```

说明：

- `{{1.analysis_prompt}}` 是前端已经拼好的 prompt，已经约束“输出精简、不要明确仓位比例”，直接映射即可
- 如果你愿意单独维护系统提示词，可以参考同目录下的 `system_prompt.md`
- `response_schema.json` 的内容可以直接复制到 `responseJsonSchema`

## 第 4 步：Webhook response 模块

最后添加 `Webhooks > Webhook response` 模块。

推荐设置：

- Status: `200`
- Body: 直接返回 HTTP 模块的响应体原文
- Content-Type: `application/json`

最简单的做法是把 HTTP 模块的 `Body` 字段原样传回去，不需要再在 Make 里手动拆 JSON。前端现在已经支持解析 Gemini REST 的原始响应格式。

## 第 5 步：把新 webhook URL 配到前端

在 [index.html](/Users/apple/Desktop/aguaixuangu-main/index.html:7067) 的 `APP_RUNTIME` 中填写：

```js
makeExecutionAnalysisWebhook: "你的新 Make webhook URL",
geminiModel: "gemini-3-flash-preview",
```

兼容旧字段：

```js
MAKE_COM_AI_WEBHOOK_URL: "你的新 Make webhook URL",
```

但更推荐使用 `makeExecutionAnalysisWebhook`。

## 第 6 步：验证是否真的能给前端返回结果

先运行自检脚本：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL"
```

脚本通过时，至少说明：

- webhook 可访问
- Make 场景在监听
- Gemini 有返回
- 返回结果能被前端当前逻辑解析

然后再打开页面，点击“AI 交易执行分析”按钮做前端验证。

## 排障要点

### 1. 返回 `410`

说明 webhook 没有连接到活动场景，或场景已失效太久。

处理：

- 确认 Scenario 已保存并开启
- 确认当前 webhook 属于这个 Scenario
- 不要继续使用旧 URL，直接重新复制最新 webhook URL

### 2. 返回 `Accepted`

说明场景只是收到了请求，但没有通过 `Webhook response` 同步把结果回传。

处理：

- 确认最后一个模块是 `Webhook response`
- 确认它返回的是 HTTP 模块的响应体
- 不要把场景做成异步队列式返回

### 3. 返回 401 / 403

说明 Gemini API Key、权限或额度有问题。

### 4. 页面仍显示规则分析

说明 Make / Gemini 没有返回可解析的结构化结果。此时前端会自动回退到本地规则分析，并在弹窗里附上排障提示。

## 文件清单

- [response_schema.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/response_schema.json)
- [system_prompt.md](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/system_prompt.md)
- [sample_payload.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/sample_payload.json)
- [verify_make_execution_webhook.sh](/Users/apple/Desktop/aguaixuangu-main/scripts/verify_make_execution_webhook.sh)
