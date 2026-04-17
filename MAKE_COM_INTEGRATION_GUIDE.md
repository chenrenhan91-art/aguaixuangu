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
| `current_price` | `{{1.current_price}}` |
| `stop_loss_price` | `{{1.stop_loss_price}}` |
| `take_profit_1` | `{{1.take_profit_1}}` |
| `take_profit_2` | `{{1.take_profit_2}}` |
| `risk_reward_ratio` | `{{1.risk_reward_ratio}}` |
| `volatility_10` | `{{1.volatility_10}}` |
| `industry` | `{{1.industry}}` |
| `event_text` | `{{1.event_text}}` |

### 第 3 步：调用 AI 模型

#### 方案 A：使用 OpenAI

1. 搜索并添加 **"OpenAI - Create a message"** 模块
2. 配置：
   - **Connection**：选择或新建 OpenAI 连接（需要 API Key）
   - **Model**：`gpt-4` 或 `gpt-3.5-turbo`
   - **System message**：
     ```
     你是一个专业的股票交易策略分析师。基于用户提供的数据，生成具体的交易执行建议。
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
     - 第一止盈位：{{take_profit_1}}
     - 第二止盈位：{{take_profit_2}}
     - 风险收益比：{{risk_reward_ratio}}
     - 波动率：{{volatility_10}}

     最近催化：{{event_text}}

     请按以下 JSON 格式生成分析结果（不要包含任何额外文本，只返回纯 JSON）：
     {
       "summary": "核心交易建议总结（一句话）",
       "highlights": ["要点1", "要点2", "要点3"],
       "key_signal": "关键信号解读",
       "trigger_points": ["触发条件1", "触发条件2"],
       "invalidation_points": ["失效条件1", "失效条件2"],
       "execution_plan": ["执行步骤1", "执行步骤2"],
       "stance": "头寸态度（看多/看空/中性）",
       "setup_quality": "结构质量评分（1-10）"
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
       "highlights": "{{4.highlights}}",
       "key_signal": "{{4.key_signal}}",
       "trigger_points": "{{4.trigger_points}}",
       "invalidation_points": "{{4.invalidation_points}}",
       "execution_plan": "{{4.execution_plan}}",
       "stance": "{{4.stance}}",
       "setup_quality": "{{4.setup_quality}}",
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
      current_price: detail.feature_map?.latest_close || 0,
      stop_loss_price: detail.risk_plan?.stop_loss_price || 0,
      take_profit_1: detail.risk_plan?.take_profit_price_1 || 0,
      take_profit_2: detail.risk_plan?.take_profit_price_2 || 0,
      risk_reward_ratio: detail.risk_plan?.risk_reward_ratio || 0,
      volatility_10: detail.feature_map?.volatility_10 || 0,
      industry: detail.industry,
      event_text: detail.events?.[0]?.title || "无特定事件催化",
      mode_id: state.selectedMode,
      user_id: state.user?.id || null,
      trade_date: snapshot.trade_date,
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
        highlights: result.data.highlights || [],
        key_signal: result.data.key_signal || "",
        trigger_points: result.data.trigger_points || [],
        invalidation_points: result.data.invalidation_points || [],
        execution_plan: result.data.execution_plan || [],
        stance: result.data.stance || "中性",
        setup_quality: result.data.setup_quality || "--",
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
       "current_price": 79.95,
       "stop_loss_price": 73.71,
       "take_profit_1": 91.18,
       "take_profit_2": 98.67,
       "risk_reward_ratio": 1.8,
       "volatility_10": 5.15,
       "industry": "电子元器件",
       "event_text": "北京市天元律师事务所关于利通电子激励计划法律意见"
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

核心交易建议：当前处于底部布局机会，建议轻仓试错。

关键观察
当前模式更看重 行业强度、资金共识、龙头扩散...

触发条件
• 量价确认突破 20 日线
• 成交额同步放大 20% 以上

失效条件
• 收盘跌破 10 日线
• 成交量委缩至平均水平以下

执行步骤
1. 轻仓试错，初始仓位不超过 1%
2. 突破确认后加仓到 2-3%
3. 收盘若跌破支撑，立即止损
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
