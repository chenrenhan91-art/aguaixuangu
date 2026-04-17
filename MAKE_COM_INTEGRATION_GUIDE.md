# Make.com AI 交易执行分析集成指南

## 🎯 目标
使用 Make.com 集成 AI 模型（OpenAI/Gemini/Claude），为当前选中的股票生成交易执行建议。

---

## 📦 前置条件

1. **Make.com 账号**：[https://make.com](https://make.com)
2. **AI 模型 API Key**：
   - OpenAI: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   - Gemini: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
   - Claude: [https://console.anthropic.com/](https://console.anthropic.com/)

---

## 🔧 Make.com 工作流配置

### 第 1 步：创建 Scenario

1. 登录 Make.com → **Create a new scenario**
2. 搜索 **"Webhooks"** 模块
3. 选择 **"Custom webhook"** → 点击 **"Add"**
4. 给 webhook 取名：`AI Trading Analysis`
5. **启用 webhook** → 复制 Webhook URL，格式如下：
   ```
   https://hook.make.com/xxxxxxxxxxxxx
   ```
   **保存这个 URL，后面会在前端代码中用到**

### 第 2 步：添加数据处理模块

1. 点击 Webhook 右边的 **"+"** 
2. 搜索 **"Set multiple variables"** → 添加模块
3. 配置变量映射（这样确保数据完整传递）：

| 变量名 | 映射值 |
|--------|--------|
| `symbol` | `{{1.symbol}}` |
| `stock_name` | `{{1.stock_name}}` |
| `response_schema_version` | `{{1.response_schema_version}}` |
| `current_price` | `{{1.current_price}}` |
| `stop_loss_price` | `{{1.stop_loss_price}}` |
| `take_profit_price_1` | `{{1.take_profit_price_1}}` |
| `take_profit_price_2` | `{{1.take_profit_price_2}}` |
| `risk_reward_ratio` | `{{1.risk_reward_ratio}}` |
| `industry` | `{{1.industry}}` |
| `trade_date` | `{{1.trade_date}}` |
| `analysis_context_json` | `{{1.analysis_context_json}}` |
| `analysis_prompt` | `{{1.analysis_prompt}}` |

### 第 3 步：调用 AI 模型

#### 方案 A：使用 OpenAI

1. 搜索并添加 **"OpenAI - Create a message"** 模块
2. 配置：
   - **Connection**：选择或新建 OpenAI 连接（需要 API Key）
   - **Model**：`gpt-4` 或 `gpt-3.5-turbo`
   - **System message**：
     ```
     你是 A 股交易执行分析助手。基于用户提供的数据，输出精简、直接的执行分析。
     请务必返回有效的 JSON 格式。
     ```
   - **User message**：
     ```
     股票信息：
     - 代码：{{symbol}}
     - 名称：{{stock_name}}
     - 当前价格：{{current_price}}
     - 所属行业：{{industry}}

     风险指标：
     - 止损价：{{stop_loss_price}}
     - 第一止盈位：{{take_profit_price_1}}
     - 第二止盈位：{{take_profit_price_2}}
     - 风险收益比：{{risk_reward_ratio}}
     - 波动率：{{volatility_10}}

     最近催化：{{event_text}}

     请按以下 JSON 格式生成分析结果（不要包含任何额外文本，只返回纯 JSON）：
     {
       "summary": "不超过两句的结论",
       "technical_judgment": "当前技术面判断",
       "stop_loss_price": 0,
       "take_profit_price_1": 0,
       "take_profit_price_2": 0,
       "invalidation_points": ["失效条件1", "失效条件2"],
       "action_note": "一句执行提醒，不要写明确仓位比例",
       "confidence": 0.8,
       "model": "gpt-4",
       "generated_at": "2026-04-17T15:30:00+08:00"
     }
     ```

#### 方案 B：使用 Gemini

1. 搜索并添加 **"Google Generative AI - Generate content"** 模块
2. 配置类似，将 system message 和 user message 合并到 prompt 中

#### 方案 C：使用 Claude

1. 搜索并添加 **"Anthropic Claude - Create a message"** 模块
2. 配置类似

### 第 4 步：JSON 解析

1. 添加 **"Parse JSON"** 模块
2. **String to parse**：
   ```
   {{3.choices[0].message.content}}
   ```
   （如果用 Gemini 或 Claude，调整路径即可）

### 第 5 步：返回结果

1. 添加 **"Respond to webhook"** 模块
2. **Body** 配置为：
   ```json
   {
     "status": "success",
     "data": {
       "summary": "{{4.summary}}",
       "technical_judgment": "{{4.technical_judgment}}",
       "stop_loss_price": {{4.stop_loss_price}},
       "take_profit_price_1": {{4.take_profit_price_1}},
       "take_profit_price_2": {{4.take_profit_price_2}},
       "invalidation_points": "{{4.invalidation_points}}",
       "action_note": "{{4.action_note}}",
       "model": "gpt-4",
       "confidence": 0.82,
       "generated_at": "{{now()}}"
     }
   }
   ```

3. **Status code**：`200`

### 第 6 步：错误处理（可选）

1. 在 AI 模块和 Parse JSON 之间添加 **"Error Handler"**
2. 配置回退方案，返回默认分析结果

---

## 💻 前端代码修改

### 修改 index.html 中的 requestExecutionAnalysis 函数

找到第 7481 行的函数，替换为：

```javascript
async function requestExecutionAnalysis(detail, signal) {
  if (!detail) {
    return null;
  }

  // Make.com webhook URL（从 Make.com 中复制）
  const MAKE_COM_WEBHOOK_URL = "https://hook.make.com/YOUR_WEBHOOK_ID_HERE";
  
  // 如果没有配置 webhook，使用本地规则
  if (!MAKE_COM_WEBHOOK_URL || MAKE_COM_WEBHOOK_URL.includes("YOUR_WEBHOOK_ID")) {
    console.warn("Make.com webhook 未配置，使用本地规则分析");
    return detail.ai_risk_analysis || null;
  }

  try {
    // 准备发送给 Make.com 的数据
    const payload = {
      symbol: detail.symbol,
      stock_name: detail.name,
      response_schema_version: "execution-analysis-v2",
      current_price: detail.feature_map?.latest_close || 0,
      stop_loss_price: detail.risk_plan?.stop_loss_price || 0,
      take_profit_price_1: detail.risk_plan?.take_profit_price_1 || 0,
      take_profit_price_2: detail.risk_plan?.take_profit_price_2 || 0,
      risk_reward_ratio: detail.risk_plan?.risk_reward_ratio || 0,
      industry: detail.industry,
      event_text: detail.events?.[0]?.title || "无特定事件催化",
      mode_id: state.selectedMode,
      user_id: state.user?.id || null,
      trade_date: snapshot.trade_date
    };

    // 调用 Make.com webhook
    const response = await fetch(MAKE_COM_WEBHOOK_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      console.error(`Make.com 请求失败: ${response.status}`);
      return detail.ai_risk_analysis || null;
    }

    const result = await response.json();
    
    // 转换 Make.com 返回结果为本地格式
    if (result?.data) {
      return {
        status: "ai_generated",
        model: result.data.model || "gpt-4",
        confidence: result.data.confidence || 0.82,
        summary: result.data.summary || "",
        technical_judgment: result.data.technical_judgment || "",
        stop_loss_price: result.data.stop_loss_price || 0,
        take_profit_price_1: result.data.take_profit_price_1 || 0,
        take_profit_price_2: result.data.take_profit_price_2 || 0,
        invalidation_points: result.data.invalidation_points || [],
        action_note: result.data.action_note || "",
        source: "make_com",
        generated_at: result.data.generated_at || new Date().toISOString(),
      };
    }

    return detail.ai_risk_analysis || null;
  } catch (error) {
    console.error("AI 执行分析请求异常:", error);
    // 异常时降级到本地规则
    return detail.ai_risk_analysis || null;
  }
}
```

---

## 🧪 测试步骤

### 本地测试

1. **使用 curl 测试 webhook**：
   ```bash
   curl -X POST "https://hook.make.com/YOUR_WEBHOOK_ID_HERE" \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "603629",
       "stock_name": "利通电子",
       "response_schema_version": "execution-analysis-v2",
       "current_price": 79.95,
       "stop_loss_price": 73.71,
       "take_profit_price_1": 91.18,
       "take_profit_price_2": 98.67,
       "risk_reward_ratio": 1.8,
       "industry": "电子元器件",
       "trade_date": "2026-04-17"
     }'
   ```

2. **在页面上测试**：
   - 打开网页，选中任意股票
   - 点击"AI 交易执行分析"按钮
   - 查看浏览器控制台 (`F12` → `Console`) 是否有错误
   - 等待 AI 响应（通常 5-15 秒）

### 调试技巧

- **启用详细日志**：在浏览器控制台运行：
  ```javascript
  localStorage.setItem("DEBUG_AI_ANALYSIS", "true");
  ```

- **查看网络请求**：`F12` → `Network` → 找到对应 webhook 的请求，查看 Response

---

## 🔐 安全建议

1. **不要在代码中暴露 API Key**
   - Make.com 中配置 API Key，不要在前端代码中显示

2. **使用环境变量**（推荐）
   - 在 Make.com 中配置 webhook URL 作为环境变量
   - 在前端从后端配置 API 获取 webhook URL

3. **添加速率限制**
   - 在 Make.com 中配置每分钟最多请求数限制
   - 防止滥用

---

## 📊 预期效果

点击"AI 交易执行分析"后，模态框应显示：

```
AI 交易执行分析
━━━━━━━━━━━━━━━━━━━━━━━━━━
生成 2026-04-17 15:30  GPT-4  置信度 82 / 100

[看多] [结构优秀] [事件驱动]

核心交易建议：技术结构仍偏强，但当前位置不宜追高。若回踩不破关键位，可继续跟踪。

技术面判断
价格仍运行在关键均线上方，但短线已有一定乖离，追价性价比一般。

关键价位
• 止损位：1620.00 元
• 第一止盈：1750.00 元
• 第二止盈：1810.00 元

失效条件
• 收盘跌破 1620 元
• 放量转弱且次日无法收回关键位

执行提醒
若无法放量站稳前高，宁可继续观察，也不要追价。
```

---

## 🐛 常见问题

### Q1: Make.com 请求总是超时
**A**: 
- 检查网络连接
- 增加 timeout：在 fetch 中添加 `{ timeout: 30000 }`
- 检查 Make.com 中 AI 模块的响应时间

### Q2: AI 返回的 JSON 格式不对
**A**:
- 检查 Make.com 中的 AI Prompt 是否要求纯 JSON 返回
- 在 Parse JSON 之前添加字符串清洗模块
- 使用 `JSON.parse()` 做容错处理

### Q3: 频繁收到 "暂时不可用" 错误
**A**:
- 确认 Make.com webhook 状态为"Running"
- 检查 OpenAI/Gemini/Claude API 配额
- 查看 Make.com 中的 Activity 日志找出具体错误

---

## 📚 相关资源

- Make.com 官方文档：https://www.make.com/en/help
- OpenAI API 文档：https://platform.openai.com/docs
- Gemini API 文档：https://ai.google.dev/
- Claude API 文档：https://docs.anthropic.com/
