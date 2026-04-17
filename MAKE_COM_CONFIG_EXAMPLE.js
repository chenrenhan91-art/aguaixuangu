/**
 * APP_RUNTIME 配置示例 - Make.com AI 交易执行分析
 * 
 * 这是一个配置模板，展示如何在网页中配置 Make.com webhook URL
 */

// ============================================================================
// 方法 1：在 HTML 页面中直接配置（最简单）
// ============================================================================

// 在 index.html 中找到 APP_RUNTIME 初始化部分（通常在 <script> 标签开头）
// 添加以下配置：

const APP_RUNTIME = {
  // ... 其他配置 ...
  
  // Make.com AI 分析 webhook URL
  // 获取方式：登录 Make.com → 创建 Scenario → 添加 Webhook → 复制 webhook URL
  MAKE_COM_AI_WEBHOOK_URL: "https://hook.make.com/xxxxxxxxxxxxxxxxxxxxxx",
  
  // ... 其他配置 ...
};


// ============================================================================
// 方法 2：从后端接口动态加载配置（推荐用于生产环境）
// ============================================================================

// 在页面初始化时添加以下函数调用：

async function loadRuntimeConfigFromBackend() {
  try {
    const response = await fetch("/api/config/runtime");
    if (response.ok) {
      const config = await response.json();
      Object.assign(APP_RUNTIME, config);
      console.log("✓ 运行时配置已加载");
    }
  } catch (error) {
    console.warn("⚠ 无法从后端加载配置，使用默认值", error);
  }
}

// 在页面加载完成后调用
document.addEventListener("DOMContentLoaded", loadRuntimeConfigFromBackend);


// ============================================================================
// 方法 3：使用 Chrome DevTools 运行时注入
// ============================================================================

// 打开浏览器 F12 → Console → 粘贴以下代码：

// 一行代码快速配置（用于测试）
APP_RUNTIME.MAKE_COM_AI_WEBHOOK_URL = "https://hook.make.com/xxxxx";

// 验证配置是否生效
console.log("当前 Make.com webhook URL:", APP_RUNTIME.MAKE_COM_AI_WEBHOOK_URL);


// ============================================================================
// Make.com Webhook URL 获取步骤
// ============================================================================

/**
 * Step 1：登录 Make.com
 * - 网址：https://make.com
 * - 登录你的账号
 * 
 * Step 2：创建新的 Scenario
 * - 点击 "Create a new scenario"
 * - 搜索 "Webhooks" 模块
 * - 选择 "Custom webhook"
 * 
 * Step 3：获取 Webhook URL
 * - 在 webhook 模块中点击 "Create a webhook"
 * - 复制生成的 URL，格式如下：
 *   https://hook.make.com/xxxxxxxxxxxxxxxxxxxxxx
 * 
 * Step 4：测试 Webhook
 * - 使用 curl 命令测试：
 *   curl -X POST "https://hook.make.com/xxxxx" \
 *     -H "Content-Type: application/json" \
 *     -d '{"symbol":"603629","stock_name":"利通电子"}'
 * 
 * Step 5：配置前端
 * - 将 URL 填入 APP_RUNTIME 的 MAKE_COM_AI_WEBHOOK_URL 字段
 */


// ============================================================================
// Make.com Workflow 配置架构
// ============================================================================

/**
 * 工作流顺序：
 * 
 * 1. [Webhook] 接收来自前端的数据
 *    └─ 接收字段：symbol, stock_name, current_price, stop_loss_price 等
 * 
 * 2. [Set Variables] 整理数据
 *    └─ 确保后续模块能正确读取数据
 * 
 * 3. [OpenAI / Gemini / Claude] 调用 AI 模型
 *    └─ 输入：股票数据 + Prompt
 *    └─ 输出：JSON 格式的交易分析建议
 * 
 * 4. [Parse JSON] 解析 AI 返回的 JSON
 *    └─ 确保数据格式正确
 * 
 * 5. [Respond to webhook] 返回结果给前端
 *    └─ 返回格式：{ status: "success", data: {...} }
 */


// ============================================================================
// 前端调用示例
// ============================================================================

/**
 * 当用户点击"AI 交易执行分析"按钮时，会自动：
 * 
 * 1. 收集当前选中股票的数据
 * 2. 检查 APP_RUNTIME.MAKE_COM_AI_WEBHOOK_URL 是否已配置
 * 3. 发送 POST 请求到 Make.com webhook
 * 4. 等待 Make.com 中的 AI 模型处理
 * 5. 显示返回的交易建议
 * 
 * 返回数据结构：
 * {
 *   "status": "ai_generated",
 *   "model": "gpt-4",
 *   "confidence": 0.82,
 *   "summary": "当前处于底部布局机会，建议轻仓试错。",
 *   "highlights": ["要点1", "要点2", "要点3"],
 *   "key_signal": "关键信号解读",
 *   "trigger_points": ["触发条件1", "触发条件2"],
 *   "invalidation_points": ["失效条件1", "失效条件2"],
 *   "execution_plan": ["执行步骤1", "执行步骤2"],
 *   "stance": "看多",
 *   "setup_quality": "优秀",
 *   "source": "make_com_ai",
 *   "generated_at": "2026-04-17T15:30:00Z"
 * }
 */


// ============================================================================
// 故障排查
// ============================================================================

/**
 * 问题 1：点击按钮后没有响应
 * 解决：
 * - 检查浏览器 Console 是否有错误
 * - 确认 APP_RUNTIME.MAKE_COM_AI_WEBHOOK_URL 已配置
 * - 运行：console.log(APP_RUNTIME.MAKE_COM_AI_WEBHOOK_URL)
 * 
 * 问题 2：webhook 请求超时
 * 解决：
 * - 检查 Make.com 中是否有错误
 * - 在 Make.com Dashboard 中查看 Scenario 的最近执行记录
 * - 检查 AI 模型（OpenAI/Gemini）是否正常工作
 * 
 * 问题 3：返回的数据格式不对
 * 解决：
 * - 确认 Make.com 中的 "Respond to webhook" 模块返回了正确的 JSON
 * - 检查 AI Prompt 是否要求返回纯 JSON
 * - 添加 "Parse JSON" 模块进行数据验证
 * 
 * 问题 4：AI 分析内容不理想
 * 解决：
 * - 优化 Make.com 中 AI 模块的 Prompt
 * - 尝试更强大的模型（gpt-4 > gpt-3.5, claude-3-opus > claude-3-sonnet）
 * - 增加 Prompt 中的例子和指引
 */


// ============================================================================
// 完整配置示例
// ============================================================================

// 复制以下完整配置到你的 index.html 的 APP_RUNTIME 初始化部分：

const APP_RUNTIME_COMPLETE_EXAMPLE = {
  // 基础配置
  APP_ENV: "production",
  APP_VERSION: "1.0.0",
  
  // Supabase 配置
  SUPABASE_URL: "https://xxxxx.supabase.co",
  SUPABASE_ANON_KEY: "xxxxx",
  
  // 后端代理配置
  PROXY_BASE_URL: "https://api.example.com",
  
  // Make.com AI 交易执行分析 webhook
  // 从 https://make.com 获取你的 webhook URL
  MAKE_COM_AI_WEBHOOK_URL: "https://hook.make.com/xxxxxxxxxxxxxxxxxxxxxx",
  
  // AI 模型配置（用于直接调用，不通过 Make.com）
  AI_PROVIDER: "openai", // "openai" | "gemini" | "claude"
  AI_MODEL: "gpt-4",
  AI_API_KEY: "", // 不要在前端暴露 API Key！
};

// ============================================================================
