# Make.com 前端集成指南

## Webhook 配置

**活跃 Webhook URL:**
```
https://hook.us2.make.com/gav22ypjvftehn5uvqt4hduwzlmvs8fj
```

**状态:** ✅ 已激活

---

## 前端集成代码

### 1. 环境配置 (`.env.local`)

```bash
VITE_MAKE_WEBHOOK_URL=https://hook.us2.make.com/gav22ypjvftehn5uvqt4hduwzlmvs8fj
```

### 2. API 服务模块 (`src/services/tradeAnalysis.js`)

```javascript
export class TradeAnalysisService {
  constructor() {
    this.webhookUrl = import.meta.env.VITE_MAKE_WEBHOOK_URL;
  }

  /**
   * 发送股票交易数据至 Make.com 进行 AI 分析
   * @param {Object} tradeData - 交易数据对象
   * @returns {Promise<Object>} AI 分析结果
   */
  async analyzeStock(tradeData) {
    try {
      const payload = {
        symbol: tradeData.symbol,
        stock_name: tradeData.stock_name,
        current_price: tradeData.current_price,
        stop_loss_price: tradeData.stop_loss_price,
        take_profit_1: tradeData.take_profit_1,
        take_profit_2: tradeData.take_profit_2,
        risk_reward_ratio: tradeData.risk_reward_ratio,
        volatility_10: tradeData.volatility_10,
        industry: tradeData.industry,
        event_text: tradeData.event_text,
        mode_id: tradeData.mode_id || 'neutral',
        user_id: tradeData.user_id || null,
        trade_date: new Date().toISOString().split('T')[0]
      };

      const response = await fetch(this.webhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Make.com 返回 "Accepted%" 状态码
      const text = await response.text();
      
      if (text.includes('Accepted')) {
        return {
          status: 'accepted',
          message: '分析请求已提交至 Gemini AI',
          timestamp: new Date().toISOString()
        };
      }

      return JSON.parse(text);
    } catch (error) {
      console.error('Trade analysis error:', error);
      throw new Error(`AI 分析失败: ${error.message}`);
    }
  }

  /**
   * 批量分析多只股票
   * @param {Array} tradeDataArray - 交易数据数组
   * @returns {Promise<Array>} 分析结果数组
   */
  async analyzeBulk(tradeDataArray) {
    const results = await Promise.all(
      tradeDataArray.map(data => this.analyzeStock(data))
    );
    return results;
  }
}

// 导出单例
export const tradeAnalysisService = new TradeAnalysisService();
```

### 3. React 组件示例 (`src/components/StockAnalyzer.jsx`)

```jsx
import { useState } from 'react';
import { tradeAnalysisService } from '../services/tradeAnalysis';

export function StockAnalyzer() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData(e.target);
      const tradeData = {
        symbol: formData.get('symbol'),
        stock_name: formData.get('stock_name'),
        current_price: parseFloat(formData.get('current_price')),
        stop_loss_price: parseFloat(formData.get('stop_loss_price')),
        take_profit_1: parseFloat(formData.get('take_profit_1')),
        take_profit_2: parseFloat(formData.get('take_profit_2')),
        risk_reward_ratio: parseFloat(formData.get('risk_reward_ratio')),
        volatility_10: parseFloat(formData.get('volatility_10')),
        industry: formData.get('industry'),
        event_text: formData.get('event_text'),
        mode_id: formData.get('mode_id'),
      };

      const analysisResult = await tradeAnalysisService.analyzeStock(tradeData);
      setResult(analysisResult);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="stock-analyzer">
      <h2>AI 股票交易分析</h2>
      
      <form onSubmit={handleAnalyze} className="analysis-form">
        <div className="form-group">
          <label>股票代码</label>
          <input name="symbol" required placeholder="e.g., 603629" />
        </div>

        <div className="form-group">
          <label>股票名称</label>
          <input name="stock_name" required placeholder="e.g., 利通电子" />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>当前价格</label>
            <input name="current_price" type="number" step="0.01" required />
          </div>
          <div className="form-group">
            <label>止损价</label>
            <input name="stop_loss_price" type="number" step="0.01" required />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>第一目标</label>
            <input name="take_profit_1" type="number" step="0.01" required />
          </div>
          <div className="form-group">
            <label>第二目标</label>
            <input name="take_profit_2" type="number" step="0.01" required />
          </div>
        </div>

        <div className="form-group">
          <label>风险收益比</label>
          <input name="risk_reward_ratio" type="number" step="0.01" required />
        </div>

        <div className="form-group">
          <label>10日波动率 (%)</label>
          <input name="volatility_10" type="number" step="0.01" required />
        </div>

        <div className="form-group">
          <label>行业</label>
          <input name="industry" required placeholder="e.g., 电子元器件" />
        </div>

        <div className="form-group">
          <label>事件信息</label>
          <textarea name="event_text" placeholder="输入相关事件信息" rows="3" />
        </div>

        <div className="form-group">
          <label>交易模式</label>
          <select name="mode_id" defaultValue="neutral">
            <option value="neutral">中立 (Neutral)</option>
            <option value="aggressive">激进 (Aggressive)</option>
            <option value="conservative">保守 (Conservative)</option>
          </select>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? '分析中...' : '提交分析'}
        </button>
      </form>

      {result && (
        <div className="result">
          <h3>分析结果</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}

      {error && (
        <div className="error">
          <p>错误: {error}</p>
        </div>
      )}
    </div>
  );
}
```

### 4. Vue 组件示例 (`src/components/StockAnalyzer.vue`)

```vue
<template>
  <div class="stock-analyzer">
    <h2>AI 股票交易分析</h2>
    
    <form @submit.prevent="handleAnalyze" class="analysis-form">
      <div class="form-group">
        <label>股票代码</label>
        <input v-model="form.symbol" required placeholder="e.g., 603629" />
      </div>

      <div class="form-group">
        <label>股票名称</label>
        <input v-model="form.stock_name" required placeholder="e.g., 利通电子" />
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>当前价格</label>
          <input v-model.number="form.current_price" type="number" step="0.01" required />
        </div>
        <div class="form-group">
          <label>止损价</label>
          <input v-model.number="form.stop_loss_price" type="number" step="0.01" required />
        </div>
      </div>

      <!-- 其他字段... -->

      <button type="submit" :disabled="loading">
        {{ loading ? '分析中...' : '提交分析' }}
      </button>
    </form>

    <div v-if="result" class="result">
      <h3>分析结果</h3>
      <pre>{{ JSON.stringify(result, null, 2) }}</pre>
    </div>

    <div v-if="error" class="error">
      <p>错误: {{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { tradeAnalysisService } from '../services/tradeAnalysis';

const loading = ref(false);
const result = ref(null);
const error = ref(null);

const form = ref({
  symbol: '',
  stock_name: '',
  current_price: 0,
  stop_loss_price: 0,
  take_profit_1: 0,
  take_profit_2: 0,
  risk_reward_ratio: 0,
  volatility_10: 0,
  industry: '',
  event_text: '',
  mode_id: 'neutral'
});

const handleAnalyze = async () => {
  loading.value = true;
  error.value = null;

  try {
    const analysisResult = await tradeAnalysisService.analyzeStock(form.value);
    result.value = analysisResult;
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.stock-analyzer {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.analysis-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-family: inherit;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

button {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result {
  margin-top: 20px;
  padding: 15px;
  background: #f0f0f0;
  border-radius: 4px;
}

.error {
  margin-top: 20px;
  padding: 15px;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
}
</style>
```

---

## 工作流执行流程

```
用户提交表单
    ↓
POST 到 Webhook URL
    ↓
Make.com 接收数据
    ↓
Set Multiple Variables (数据映射)
    ↓
Google Gemini AI 3.1 Pro (分析)
    ↓
Parse JSON (结果解析)
    ↓
Webhook Response (返回结果)
    ↓
前端接收结果并显示
```

---

## 测试命令

```bash
# 发送测试请求
curl -X POST "https://hook.us2.make.com/gav22ypjvftehn5uvqt4hduwzlmvs8fj" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol":"603629",
    "stock_name":"利通电子",
    "current_price":79.95,
    "stop_loss_price":73.71,
    "take_profit_1":91.18,
    "take_profit_2":98.67,
    "risk_reward_ratio":1.8,
    "volatility_10":5.15,
    "industry":"电子元器件",
    "event_text":"北京市天元律师事务所关于利通电子激励计划法律意见",
    "mode_id":"aggressive",
    "user_id":null,
    "trade_date":"2026-04-17"
  }'
```

---

## 配置清单

- ✅ Webhook URL 创建并测试
- ✅ Google Gemini AI 3.1 Pro 连接配置
- ✅ 工作流模块链完整
- ✅ 场景已激活
- ✅ API Key 已配置

---

## 故障排查

| 问题 | 解决方案 |
|------|--------|
| 请求被拒绝 | 检查 CORS 设置，确保 webhook URL 正确 |
| 超时 | Gemini AI 响应较慢，增加超时时间 |
| JSON 解析错误 | 确认响应格式正确，检查 Parse JSON 配置 |
| API 配额不足 | 检查 Gemini API 配额和计费 |

---

## 后续优化

1. **缓存机制** - 对相同查询实现本地缓存
2. **重试逻辑** - 实现指数退避重试
3. **速率限制** - 限制单位时间请求数
4. **结果聚合** - 批量请求优化
5. **监控告警** - 集成日志和监控系统
