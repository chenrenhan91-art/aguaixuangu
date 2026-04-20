/**
 * APP_RUNTIME 配置示例 - Supabase Function + Make AI 交易执行分析
 *
 * 当前正式链路：
 * 前端 -> Supabase Edge Function -> Make webhook -> Gemini
 *
 * 注意：
 * 1. 不要再把 Make webhook URL 写到前端。
 * 2. 前端只配置 Supabase 和受保护 Function 地址。
 * 3. Make webhook URL 只放在 Supabase Function 环境变量里。
 */

const APP_RUNTIME = {
  // ... 其他配置 ...

  // 受保护的 Supabase Function 地址
  executionAnalysisProxyUrl: "https://<project-ref>.supabase.co/functions/v1/stocks-execution-analysis",

  // Supabase Auth 配置
  supabaseUrl: "https://<project-ref>.supabase.co",
  supabaseAnonKey: "你的 Supabase anon key",

  // 邮箱确认后的回跳地址
  authEmailRedirectTo: "https://你的站点地址/",

  // ... 其他配置 ...
};

/**
 * Supabase Function 环境变量：
 *
 * SUPABASE_URL=https://<project-ref>.supabase.co
 * SUPABASE_SERVICE_ROLE_KEY=你的 service role key
 * MAKE_EXECUTION_ANALYSIS_WEBHOOK_URL=https://hook.make.com/xxxxxxxxxxxxxxxxxxxxxx
 */

/**
 * 邀请码相关：
 *
 * - 注册时前端会调用 `supabase.auth.signUp`
 * - 邀请码通过 `options.data.invite_code` 传给 Supabase
 * - `reserve_invite_code_for_new_user(jsonb)` Hook 会在注册前校验邀请码
 * - 只有邮箱已验证且邀请码 claim 有效的用户，才能调用受保护 AI 分析接口
 */
