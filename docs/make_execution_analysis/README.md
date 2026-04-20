# Make + Gemini 个股交易分析接入说明

这套说明对应页面里的“AI 交易执行分析”功能。

当前版本已经升级为：

- 用户通过前端输入股票代码发起分析
- 前端按输入代码构造请求，不再依赖当前选中的候选股
- 在一个 Make Scenario 内完成多 agent 风格分析
- 不需要拆多个 Make 环境
- AI 返回结果中必须包含多 agent 的有效输出，前端会自动展开显示

## 当前前端协议

前端现在发送的 payload 核心字段包括：

- `analysis_type`
- `requested_symbol`
- `stock_code`
- `selected_mode_id`
- `matched_snapshot`
- `market_snapshot`
- `analysis_context_json`
- `analysis_prompt`
- `response_schema_version`

当前 schema 版本：

- `execution-analysis-v3`

相关文件：

- [README.md](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/README.md)
- [response_schema.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/response_schema.json)
- [sample_payload.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/sample_payload.json)
- [system_prompt.md](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/system_prompt.md)
- [verify_make_execution_webhook.sh](/Users/apple/Desktop/aguaixuangu-main/scripts/verify_make_execution_webhook.sh)

## 推荐 Make 结构

推荐只保留 3 个模块：

1. `Webhooks > Custom webhook`
2. `HTTP > Make a request`
3. `Webhooks > Webhook response`

如果你当前场景里还有 `JSON > Parse JSON`，建议先删掉。前端已经兼容：

- Make 直接返回最终 JSON
- Make 直接返回 Gemini 原始 `candidates -> parts -> text`
- 双层 JSON 字符串

所以这条链路现在不需要额外的 JSON 解析模块。

## 重新设置 Make 环境的详细步骤

## 第 1 步：新建或清理 Scenario

如果你当前场景已经比较乱，最稳妥的方式是直接新建一个干净 Scenario。

目标结构只保留：

1. `Webhooks > Custom webhook`
2. `HTTP > Make a request`
3. `Webhooks > Webhook response`

如果你想继续沿用旧场景：

1. 打开旧场景
2. 删除旧的 `JSON > Parse JSON`
3. 删除任何只返回 `ok`、`success`、`accepted` 的中间调试模块
4. 确保最后一个模块一定是 `Webhook response`
5. 打开右上角 `Active`

## 第 2 步：配置 Custom webhook

1. 点击左侧第一个模块 `Webhooks`
2. 选择 `Custom webhook`
3. 新建一个 webhook，名字建议填：

```text
ai_execution_analysis
```

4. 保存后复制生成的 webhook URL
5. 点击底部 `Run once`

这一步的目标是让 Make 开始监听，并接收一次真实样本。

然后在仓库根目录运行：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL" \
  "./docs/make_execution_analysis/sample_payload.json"
```

Make 收到样本后，请确认 webhook 中已经能看到这些字段：

- `stock_code`
- `requested_symbol`
- `analysis_context_json`
- `analysis_prompt`
- `response_schema_version`

## 第 3 步：配置 HTTP > Make a request

点击第二个模块 `HTTP`，按下面填写。

### 基础配置

- Method: `POST`
- URL:

```text
https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent
```

- Headers:

```text
x-goog-api-key: 你的 Gemini API Key
Content-Type: application/json
```

- Body type: `Raw`
- Content type: `JSON (application/json)`

### 推荐高级设置

- Parse response: `No`
- Timeout: `18` 到 `20` 秒

说明：

- 关闭 `Parse response` 后，Webhook response 可以直接把 Gemini 原始响应体回给前端，最稳。
- 前端当前会在大约 20 秒内等待同步返回，所以不要把场景做得过长。

### HTTP Body 填写方式

把下面整段粘贴到 Body。

其中：

- `{{1.analysis_prompt}}` 来自第 1 个 webhook 模块
- `responseJsonSchema` 请直接复制 [response_schema.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/response_schema.json) 的完整内容进去

```json
{
  "system_instruction": {
    "parts": [
      {
        "text": "你是 A 股个股交易分析助手，需要在单次输出中模拟 TradingAgents-CN 风格的多 agent 研判流程，但最终只能返回一个 JSON 对象。请只返回 JSON，不要返回 Markdown，不要返回代码块，不要编造缺失数据。如果证据不足，要明确写“证据不足”。"
      }
    ]
  },
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
      "type": "object"
    }
  }
}
```

注意：

1. 上面示例里的 `responseJsonSchema` 只是占位写法，实际必须替换成 [response_schema.json](/Users/apple/Desktop/aguaixuangu-main/docs/make_execution_analysis/response_schema.json) 的完整 JSON。
2. 不要再在 Make 里自己手拼股票说明文字，直接把前端传进来的 `{{1.analysis_prompt}}` 喂给 Gemini。
3. 这一步本质上是“单次 LLM 调用模拟多 agent 角色”，不是在 Make 里真的建 8 个模块。

## 第 4 步：配置 Webhook response

点击最后一个模块 `Webhooks > Webhook response`。

推荐配置：

- Status: `200`
- Content type: `application/json`
- Body: 直接映射 HTTP 模块的原始响应体

如果你在 HTTP 模块里把 `Parse response` 设成了 `No`，这里优先选择 HTTP 模块输出里的：

- `Body`
- 或 `Data`
- 或“原始响应文本”

不同 Make 界面文案可能略有差异，但原则只有一个：

- **不要只返回 `ok`**
- **不要只返回 `success`**
- **不要只返回 `accepted`**
- **要把 Gemini 的完整响应体原样回给前端**

前端现在已经能自动识别：

- 直接 JSON
- Gemini 的 `candidates`
- `parts[].text` 中包着的 JSON 字符串

## 第 5 步：更新前端 Function 地址

在 [index.html](/Users/apple/Desktop/aguaixuangu-main/index.html) 的 `APP_RUNTIME` 中填写：

```js
executionAnalysisProxyUrl: "https://<project-ref>.supabase.co/functions/v1/stocks-execution-analysis",
authEmailRedirectTo: "https://你的站点地址/",
```

同时在 Supabase Function 环境变量中填写：

```text
MAKE_EXECUTION_ANALYSIS_WEBHOOK_URL=你的 Make webhook URL
```

## 第 6 步：联调验证

先运行：

```bash
./scripts/verify_make_execution_webhook.sh "你的 Make webhook URL"
```

然后打开页面：

1. 在“个股总览”右上角输入 6 位股票代码
2. 点击“AI 交易执行分析”

你应该看到：

- 弹窗标题为 `AI 交易执行分析`
- 顶部显示股票代码和模型信息
- 正文包含 `技术面判断`
- 正文包含 `关键信号`
- 正文包含 `关键价位`
- 正文包含 `失效条件`
- 正文包含 `执行提醒`
- 如果上游返回了多 agent 字段，还会显示 `多 Agent 有效输出`

## 当前前端已经兼容的上游返回结构

为了避免“Make 已返回，但前端不显示”，前端现在已兼容这些格式：

1. 直接返回最终结构化 JSON
2. 返回：

```json
{
  "data": { ... }
}
```

3. 返回：

```json
{
  "analysis": { ... }
}
```

4. 直接返回 Gemini 原始 envelope：

```json
{
  "candidates": [
    {
      "content": {
        "parts": [
          {
            "text": "{...json...}"
          }
        ]
      }
    }
  ]
}
```

## 最常见的错误

### 错误 1：Webhook response 只返回 `ok`

结果：

- Make 显示成功
- 前端没有 AI 结果
- 弹窗只显示本地规则回退

修复：

- 把最后一个 `Webhook response` 改成返回 HTTP 模块的原始 body

### 错误 2：场景总耗时超过前端等待时间

结果：

- 页面显示超时
- Make 历史里稍后才成功

修复：

- 保持 Scenario 只用 3 个模块
- HTTP 模块 timeout 控制在 18 到 20 秒
- 不要在这条同步链路里额外插慢速抓数模块

### 错误 3：多 agent 结果字段名不一致

推荐固定使用下面这些 key：

- `market_agent`
- `news_agent`
- `fundamentals_agent`
- `social_sentiment_agent`
- `bull_case_agent`
- `bear_case_agent`
- `risk_committee`
- `trader_decision`

这样前端才能自动按角色展示。

## 建议的最终结论

你现在最稳的配置不是“多个 Make 环境分别跑不同 agent”，而是：

1. 一个 webhook 接收前端请求
2. 一个 HTTP 模块调用 Gemini
3. 一次生成里模拟多 agent 角色
4. 一个 webhook response 原样返回结果

这样配置成本最低，延迟最短，也最容易和当前前端保持一致。
