# Make.com AI 交易执行分析工作流指南

## 概览

本指南说明如何用 Make.com 自动化 AI 风控分析的生成与更新，完成从选股 → AI 分析 → 前端展示的完整闭环。

---

## 架构设计

### 核心流程

```
GitHub 快照更新
     ↓
Make.com 定时触发 (11:35/15:05)
     ↓
读取 daily_candidates_latest.json
     ↓
调用 Webhook → 本地/云端 Python 服务
     ↓
循环调用 Gemini/ChatGPT API
     ↓
生成 AI 分析并补充到快照
     ↓
输出 daily_candidates_ai_enriched.json
     ↓
前端轮询读取（自动切换）
```

### 关键文件

- `data_pipeline/ai_analysis_service.py` - AI 调用逻辑
- `make_webhook_server.py` - HTTP 服务入口
- `data/processed/daily_candidates_ai_enriched.json` - 输出快照（前端读）

---

## 本地部署步骤

### 1. 安装依赖

```bash
pip install flask requests
# 或更新 requirements 文件
echo "flask>=2.3.0" >> requirements-pipeline.txt
echo "requests>=2.31.0" >> requirements-pipeline.txt
```

### 2. 配置 API Key

```bash
# .env 或环境变量
export GEMINI_API_KEY="你的 Gemini API Key"
# 或
export OPENAI_API_KEY="你的 OpenAI API Key"
```

### 3. 启动 Webhook 服务

```bash
# 本地测试
python make_webhook_server.py

# 生产环境（使用 gunicorn）
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 make_webhook_server.py
```

### 4. 测试 API 端点

```bash
# 健康检查
curl http://localhost:5000/health

# 触发快照增强
curl -X POST http://localhost:5000/api/enrich_snapshot \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_path": "data/processed/daily_candidates_latest.json",
    "ai_model": "gemini",
    "max_stocks": 3
  }'
```

---

## Make.com 工作流配置

### Make.com 场景模板

#### 模块 1: 定时触发（每天 11:35 和 15:05）

```
Trigger: Schedule
Time: 11:35 AM & 3:05 PM (Asia/Shanghai)
Repeat: Daily
```

#### 模块 2: 读取 GitHub 快照

```
Module: GitHub / Get a file content
Repository: chenrenhan91-art/aguaixuangu
Branch: main
Path: data/processed/daily_candidates_latest.json
```

#### 模块 3: 调用 Webhook 服务

```
Module: HTTP / Make a request
URL: https://your-server.com/api/enrich_snapshot
  或 http://localhost:5000/api/enrich_snapshot (如果本地)
Method: POST
Headers:
  Content-Type: application/json
Body (JSON):
{
  "snapshot_path": "data/processed/daily_candidates_latest.json",
  "ai_model": "gemini",
  "max_stocks": 10
}
```

#### 模块 4: 将结果推送回 GitHub

```
Module: GitHub / Create or Update a file
Repository: chenrenhan91-art/aguaixuangu
Branch: main
Path: data/processed/daily_candidates_ai_enriched.json
File Content: {{3.output_path_content}}  # 从模块 3 取输出
Commit Message: "feat: update AI trading analysis - {{now}}"
```

#### 模块 5: Webhook 通知（可选）

```
Module: Webhooks / Custom webhook
Send to: your-slack-channel 或 飞书/钉钉
Message: "✓ AI 分析已更新（{{now}}）"
```

---

## 前端适配

### 修改 index.html

在 `loadLatestSnapshot()` 中增加优先级：

```javascript
async function loadLatestSnapshot() {
  const paths = [
    'data/processed/daily_candidates_ai_enriched.json',  // 优先读 AI 版本
    'data/processed/daily_candidates_latest.json'         // 回退到基础版本
  ];
  
  for (const path of paths) {
    try {
      const response = await fetch(path);
      if (response.ok) {
        snapshot = await response.json();
        console.log(`✓ 加载快照: ${path}`);
        break;
      }
    } catch (e) {
      console.warn(`快照加载失败: ${path}`);
    }
  }
  
  if (snapshot) {
    renderMarketSentiment();
    renderSignalList();
    // ... 其他渲染
  }
}
```

---

## 成本控制建议

### API 调用优化

1. **限制股票数量**
   - 早盘（11:35）：10-15 只
   - 午盘（15:05）：5-8 只
   - 总月成本：≈ $5-15 (Gemini Flash) 或 $20-50 (ChatGPT)

2. **缓存策略**
   - 同一只股票 1 小时内不重复分析
   - 已有高质量分析的股票 skip

3. **模型选择**
   - **Gemini 2.0 Flash**：速度快（$0.05/百万 tokens），适合批量
   - **ChatGPT 4o-mini**：质量稳定（$0.15/百万 tokens）

### 预算示例

| 场景 | 日调用数 | 日成本（Gemini） | 月成本 |
|------|---------|-----------------|-------|
| 10 只 × 2 次 | 20 | $0.10 | $3 |
| 15 只 × 2 次 | 30 | $0.15 | $4.50 |
| 20 只 × 2 次 | 40 | $0.20 | $6 |

---

## 故障排查

### 常见问题

1. **API Key 错误**
   ```
   症状: "API 调用失败: 401 Unauthorized"
   解决:
   - 检查环境变量设置
   - 确认 API Key 未过期
   - 检查 API 调用配额
   ```

2. **Webhook 超时**
   ```
   症状: Make.com 触发后 60s 未响应
   解决:
   - 本地服务器配置过低 → 升级服务器
   - API 调用慢 → 改用更快的模型（Gemini Flash）
   - 股票数太多 → 减少 max_stocks 参数
   ```

3. **快照文件格式错误**
   ```
   症状: "快照文件不存在或格式无效"
   解决:
   - 检查 GitHub 快照是否生成成功
   - 验证 JSON 格式合法性
   - 检查文件权限
   ```

---

## 进阶配置

### 1. 多模型并行分析

```python
# 在 AI 服务中支持多个模型同时调用
results = {}
for model in ["gemini", "chatgpt"]:
    results[model] = generate_ai_analysis_for_record(...)
```

### 2. 与数据库同步

```javascript
// 前端可选择将 AI 分析保存到 Supabase
async function syncAiAnalysisToDb(records) {
  for (const record of records) {
    await supabase
      .from('stock_analysis')
      .upsert({
        symbol: record.symbol,
        ai_analysis: record.ai_risk_analysis,
        updated_at: new Date()
      })
  }
}
```

### 3. 钉钉/Slack 实时通知

```json
{
  "msgtype": "text",
  "text": {
    "content": "🚀 AI 分析已更新\n优先关注：半导体 × 3 只\n置信度 > 0.7：5 只"
  }
}
```

---

## 总结

通过本工作流，你已实现：

✅ **自动化分析** - 每天自动触发 AI 风控分析
✅ **降低成本** - 按需调用，批量处理
✅ **完整闭环** - 选股 → 分析 → 前端展示一体化
✅ **易于迭代** - 修改提示词或模型无需改代码

下一步可探索：
- 历史分析对比与回测
- 多模型投票机制
- 实盘执行记录关联
