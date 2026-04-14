const DEFAULT_GEMINI_MODEL = "gemini-3-pro-preview";
const GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta";

function resolveCorsOrigin(request, env) {
  return env.APP_ORIGIN || request.headers.get("Origin") || "*";
}

function buildCorsHeaders(request, env) {
  return {
    "Access-Control-Allow-Origin": resolveCorsOrigin(request, env),
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Allow-Credentials": "true",
  };
}

function jsonResponse(payload, status, request, env) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...buildCorsHeaders(request, env),
    },
  });
}

function extractJson(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed) {
    throw new Error("Gemini returned empty content.");
  }
  try {
    return JSON.parse(trimmed);
  } catch (_error) {
    const fenced = trimmed.match(/```json\s*([\s\S]+?)```/i) || trimmed.match(/```([\s\S]+?)```/i);
    if (fenced?.[1]) {
      return JSON.parse(fenced[1].trim());
    }
    const firstBrace = trimmed.indexOf("{");
    const lastBrace = trimmed.lastIndexOf("}");
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      return JSON.parse(trimmed.slice(firstBrace, lastBrace + 1));
    }
    throw new Error(`Gemini returned non-JSON content: ${trimmed.slice(0, 180)}`);
  }
}

async function callMakeJson(env, payload) {
  if (!env.MAKE_TRADE_DIAGNOSTICS_WEBHOOK) {
    throw new Error("MAKE_TRADE_DIAGNOSTICS_WEBHOOK is not configured.");
  }

  const response = await fetch(env.MAKE_TRADE_DIAGNOSTICS_WEBHOOK, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const raw = await response.text();
  if (!response.ok) {
    throw new Error(`Make HTTP ${response.status}: ${raw}`);
  }

  return raw ? JSON.parse(raw) : {};
}

async function callGeminiJson(env, systemInstruction, userPrompt, temperature = 0.2) {
  if (!env.GEMINI_API_KEY) {
    throw new Error("GEMINI_API_KEY is not configured.");
  }

  const payload = {
    systemInstruction: {
      parts: [{ text: systemInstruction }],
    },
    contents: [
      {
        role: "user",
        parts: [{ text: userPrompt }],
      },
    ],
    generationConfig: {
      temperature,
      topP: 0.9,
      responseMimeType: "application/json",
    },
  };

  const model = env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL;
  const response = await fetch(`${GEMINI_API_BASE}/models/${model}:generateContent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-goog-api-key": env.GEMINI_API_KEY,
    },
    body: JSON.stringify(payload),
  });

  const raw = await response.text();
  if (!response.ok) {
    throw new Error(`Gemini HTTP ${response.status}: ${raw}`);
  }

  const parsed = JSON.parse(raw);
  const parts = parsed?.candidates?.[0]?.content?.parts || [];
  const text = parts.map((part) => part?.text || "").join("").trim();
  return {
    parsed: extractJson(text),
    model,
  };
}

async function verifySupabaseUser(request, env) {
  const authorization = request.headers.get("Authorization") || "";
  if (!authorization.startsWith("Bearer ")) {
    return null;
  }
  if (!env.SUPABASE_URL || !env.SUPABASE_ANON_KEY) {
    return null;
  }

  const response = await fetch(`${env.SUPABASE_URL.replace(/\/$/, "")}/auth/v1/user`, {
    headers: {
      apikey: env.SUPABASE_ANON_KEY,
      Authorization: authorization,
    },
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

async function querySupabase(env, path, options = {}) {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error("Supabase service role credentials are not configured.");
  }

  const response = await fetch(`${env.SUPABASE_URL.replace(/\/$/, "")}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      Prefer: "return=representation",
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`Supabase HTTP ${response.status}: ${text}`);
  }
  return text ? JSON.parse(text) : null;
}

function buildTradeDiagnosticsSystemInstruction() {
  return (
    "你是一名A股历史交易复盘分析助理。" +
    "你的任务是基于结构化的历史交割单诊断结果，总结用户的交易风格、有效优势、主要漏洞和下一阶段优化动作。" +
    "你不能编造不存在的收益、回撤、胜率或股票案例，只能使用给定上下文。" +
    "优先级必须是：闭环交易统计 -> 盈亏对比 -> 错误模式/有效模式 -> 用户执行建议。" +
    "输出要克制、具体，适合展示在交易终端的 AI 复盘窗口。" +
    "不要给确定性承诺，不要写收益预测。" +
    "输出必须是严格 JSON，不要包含 markdown。"
  );
}

function buildTradeDiagnosticsUserPrompt(payload) {
  return JSON.stringify(
    {
      task: "基于历史交易诊断结果，生成一段可直接展示给用户的 AI 交易复盘分析。",
      requirements: [
        "不要复述所有字段，只提炼最有决策价值的结论。",
        "strengths 和 weaknesses 需要同时出现，避免只说优点或只说问题。",
        "adjustments 必须是具体动作，例如收紧买点、减少补仓、只做主线确认等。",
        "next_cycle_plan 必须按先后顺序写，适合用户下一阶段直接执行。",
        "如果闭环交易数较少或数据可信度有限，要在 summary 中体现结论强度有限。",
        "不要写仓位百分比、收益承诺或模糊表述。",
      ],
      response_schema: {
        summary: "一句话概括当前用户最值得保留的交易方式和最需要修正的问题。",
        trader_profile: "一句话概括用户当前最接近的交易者画像。",
        strengths: ["2到4条，说明当前有效的交易习惯或优势来源。"],
        weaknesses: ["2到4条，说明当前最关键的执行漏洞或亏损来源。"],
        behavior_tags: ["2到4个短标签，例如 顺势波段、追高回撤、补仓偏多。"],
        adjustments: ["3到5条，必须是可执行的优化动作，不要空话。"],
        next_cycle_plan: ["3条以内，按下一交易周期的执行顺序给计划。"],
      },
      context: payload,
    },
    null,
    2,
  );
}

function buildExecutionSystemInstruction() {
  return (
    "你是一名A股交易执行分析助理。" +
    "你的任务不是唱多，也不是直接给买卖指令，而是基于给定的规则价格位、个股结构、事件流和市场环境，生成可以直接给交易者参考的执行分析。" +
    "你必须严格使用上下文中的规则止损、止盈和价格位，不能擅自修改任何价格数字。" +
    "你必须同时写出支持交易的理由和否定交易的风险，不要只给单边看法。" +
    "判断优先级必须是：规则价格位与结构 -> 事件催化 -> 市场环境 -> 细节补充。" +
    "如果信息不足，宁可降低结论强度，也不要编造依据。" +
    "不要输出仓位百分比、盈亏比或收益承诺。" +
    "措辞要克制、具体、适合金融终端展示。" +
    "输出必须是严格 JSON，不要包含 markdown。"
  );
}

function buildExecutionUserPrompt(payload) {
  return JSON.stringify(
    {
      task: "基于规则价格位和个股上下文，生成一段更有参考价值的 AI 交易执行分析。",
      requirements: [
        "不要修改任何规则止损、止盈和价格数字。",
        "不要提仓位百分比、仓位上限、建议仓位或盈亏比。",
        "必须结合策略模式、市场环境、近期事件和特征分数一起判断，不能只复述风控位。",
        "highlights 至少覆盖结构依据、事件依据、风险依据中的两类。",
        "要明确写出什么时候值得执行，什么时候应该取消想法。",
        "trigger_points 只写可观察、可验证的现象。",
        "invalidation_points 只写会直接削弱逻辑的现象。",
        "execution_plan 按时间顺序写，优先写盘前观察、盘中确认、失效退出。",
      ],
      response_schema: {
        summary: "一句话结论，直接说明这只票当前更适合等待、跟踪确认还是顺势执行。",
        stance: "只允许 观望 / 跟踪 / 执行 之一。",
        setup_quality: "只允许 A / B / C 之一。",
        risk_bias: "keep 或 tighten。",
        key_signal: "一句话说明当前最关键的交易信号。",
        highlights: ["2到4条具体要点。"],
        trigger_points: ["2到3条，说明什么信号出现时值得继续执行。"],
        invalidation_points: ["2到3条，说明哪些现象出现就要放弃或降级。"],
        execution_plan: ["2到4条，按观察顺序给出执行动作，不要写仓位。"],
        next_step: "一句话说明下一步重点看什么。",
      },
      context: payload,
    },
    null,
    2,
  );
}

function mergeTradeDiagnostics(localDiagnostics, aiAnalysis) {
  return {
    ...localDiagnostics,
    status: "ai_live",
    ai_analysis: {
      status: "ai_live",
      model: aiAnalysis.model,
      confidence: Number(aiAnalysis.confidence || 0.68),
      summary: aiAnalysis.summary || localDiagnostics?.ai_analysis?.summary || "--",
      trader_profile: aiAnalysis.trader_profile || localDiagnostics?.style_profile?.summary || "--",
      strengths: Array.isArray(aiAnalysis.strengths) ? aiAnalysis.strengths : [],
      weaknesses: Array.isArray(aiAnalysis.weaknesses) ? aiAnalysis.weaknesses : [],
      behavior_tags: Array.isArray(aiAnalysis.behavior_tags) ? aiAnalysis.behavior_tags : [],
      adjustments: Array.isArray(aiAnalysis.adjustments) ? aiAnalysis.adjustments : [],
      next_cycle_plan: Array.isArray(aiAnalysis.next_cycle_plan) ? aiAnalysis.next_cycle_plan : [],
      source: aiAnalysis.source || "worker-gemini",
      generated_at: new Date().toISOString(),
    },
  };
}

function normalizeMakeTradeDiagnosticsResult(localDiagnostics, payload) {
  const aiAnalysis =
    payload?.ai_analysis ||
    payload?.analysis ||
    payload?.result ||
    payload?.data?.ai_analysis ||
    null;

  if (!aiAnalysis || typeof aiAnalysis !== "object") {
    throw new Error("Make returned an invalid ai_analysis payload.");
  }

  return mergeTradeDiagnostics(localDiagnostics, {
    ...aiAnalysis,
    model: aiAnalysis.model || "gemini-3.1-pro",
    source: "make-gemini",
  });
}

function buildTradeHistoryResponse(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return null;
  }
  const latest = structuredClone(rows[0].diagnostics_json || {});
  latest.recent_batches = rows
    .map((row) => row?.diagnostics_json?.latest_batch || null)
    .filter(Boolean);
  if (rows[0]?.ai_analysis_json) {
    latest.ai_analysis = rows[0].ai_analysis_json;
  }
  return latest;
}

async function saveTradeHistory(env, user, payload) {
  if (!user || !env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    return;
  }
  const latestBatch = payload?.latest_batch || {};
  const row = {
    user_id: user.id,
    email: user.email || "",
    batch_id: latestBatch.batch_id || crypto.randomUUID().slice(0, 12),
    filename: latestBatch.filename || "trade-import",
    broker: latestBatch.broker || "未识别券商",
    detected_format: latestBatch.detected_format || "unknown",
    imported_at: latestBatch.imported_at || new Date().toISOString(),
    coverage_text: payload.coverage_text || "",
    diagnostics_json: payload,
    ai_analysis_json: payload.ai_analysis || null,
  };

  await querySupabase(env, "/rest/v1/trade_diagnostics_history", {
    method: "POST",
    body: JSON.stringify(row),
  });
}

async function handleTradeDiagnosticsAnalyze(request, env, user) {
  const body = await request.json();
  const localDiagnostics = body?.local_diagnostics || body?.localDiagnostics || null;
  if (!localDiagnostics) {
    return jsonResponse({ error: "MissingDiagnostics", message: "缺少 local_diagnostics。" }, 400, request, env);
  }

  let diagnostics = localDiagnostics;
  try {
    if (env.MAKE_TRADE_DIAGNOSTICS_WEBHOOK) {
      const makePayload = await callMakeJson(env, {
        request_id: crypto.randomUUID(),
        requested_model: "gemini-3.1-pro",
        prompt_version: "make-trade-diagnostics-v1",
        generated_at: new Date().toISOString(),
        user: user
          ? {
              id: user.id,
              email: user.email || body?.email || null,
            }
          : {
              id: body?.user_id || body?.userId || null,
              email: body?.email || null,
            },
        import_meta: {
          profile_id: body?.profile_id || body?.profileId || null,
          broker: body?.broker || null,
          filename: body?.filename || null,
          detected_format: body?.detected_format || body?.detectedFormat || null,
        },
        local_diagnostics: localDiagnostics,
      });
      diagnostics = normalizeMakeTradeDiagnosticsResult(localDiagnostics, makePayload);
    } else {
      const { parsed, model } = await callGeminiJson(
        env,
        buildTradeDiagnosticsSystemInstruction(),
        buildTradeDiagnosticsUserPrompt(localDiagnostics),
        0.2,
      );
      diagnostics = mergeTradeDiagnostics(localDiagnostics, {
        ...parsed,
        model,
      });
    }
  } catch (_error) {
    try {
      const { parsed, model } = await callGeminiJson(
        env,
        buildTradeDiagnosticsSystemInstruction(),
        buildTradeDiagnosticsUserPrompt(localDiagnostics),
        0.2,
      );
      diagnostics = mergeTradeDiagnostics(localDiagnostics, {
        ...parsed,
        model,
      });
    } catch (_nestedError) {
      diagnostics = {
        ...localDiagnostics,
        ai_analysis: localDiagnostics.ai_analysis || null,
      };
    }
  }

  await saveTradeHistory(env, user, diagnostics);
  return jsonResponse({ diagnostics }, 200, request, env);
}

async function handleTradeDiagnosticsHistory(request, env, user) {
  if (!user) {
    return jsonResponse({ diagnostics: null, message: "未登录，暂无个人历史。" }, 200, request, env);
  }
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
    return jsonResponse({ diagnostics: null, message: "Supabase 未配置。" }, 200, request, env);
  }

  const rows = await querySupabase(
    env,
    `/rest/v1/trade_diagnostics_history?select=diagnostics_json,ai_analysis_json,imported_at&user_id=eq.${encodeURIComponent(user.id)}&order=imported_at.desc&limit=8`,
    { method: "GET" },
  );

  return jsonResponse({ diagnostics: buildTradeHistoryResponse(rows) }, 200, request, env);
}

async function handleExecutionAnalysis(request, env) {
  const body = await request.json();
  const detail = body?.detail || null;
  const signal = body?.signal || null;
  if (!detail) {
    return jsonResponse({ error: "MissingDetail", message: "缺少个股 detail。" }, 400, request, env);
  }

  let analysis = detail?.ai_risk_analysis || null;
  try {
    const { parsed, model } = await callGeminiJson(
      env,
      buildExecutionSystemInstruction(),
      buildExecutionUserPrompt({
        mode_id: body?.mode_id || body?.modeId,
        trade_date: body?.trade_date,
        signal,
        detail,
      }),
      0.25,
    );
    analysis = {
      status: "ai_live",
      model,
      confidence: Number(parsed.confidence || 0.68),
      summary: parsed.summary || "--",
      stance: parsed.stance || null,
      setup_quality: parsed.setup_quality || null,
      key_signal: parsed.key_signal || null,
      highlights: Array.isArray(parsed.highlights) ? parsed.highlights : [],
      trigger_points: Array.isArray(parsed.trigger_points) ? parsed.trigger_points : [],
      invalidation_points: Array.isArray(parsed.invalidation_points) ? parsed.invalidation_points : [],
      execution_plan: Array.isArray(parsed.execution_plan) ? parsed.execution_plan : [],
      next_step: parsed.next_step || "--",
      source: "worker-gemini",
      generated_at: new Date().toISOString(),
    };
  } catch (_error) {
    analysis = detail?.ai_risk_analysis || {
      status: "fallback_rules",
      model: null,
      confidence: 0.52,
      summary: "AI 执行分析暂时不可用，先按规则结构观察。",
      highlights: [],
      execution_plan: [],
      next_step: "优先观察规则位与事件流是否继续强化。",
      source: "worker-fallback",
      generated_at: new Date().toISOString(),
    };
  }

  return jsonResponse({ analysis }, 200, request, env);
}

async function routeRequest(request, env) {
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: buildCorsHeaders(request, env),
    });
  }

  if (url.pathname === "/api/health") {
    return jsonResponse(
      {
        status: "ok",
        provider: "cloudflare-worker",
        geminiConfigured: Boolean(env.GEMINI_API_KEY),
        makeTradeDiagnosticsConfigured: Boolean(env.MAKE_TRADE_DIAGNOSTICS_WEBHOOK),
        supabaseConfigured: Boolean(env.SUPABASE_URL && env.SUPABASE_SERVICE_ROLE_KEY && env.SUPABASE_ANON_KEY),
        model: env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL,
      },
      200,
      request,
      env,
    );
  }

  const user = await verifySupabaseUser(request, env);

  try {
    if (request.method === "POST" && url.pathname === "/api/trade-diagnostics/analyze") {
      return await handleTradeDiagnosticsAnalyze(request, env, user);
    }

    if (request.method === "POST" && url.pathname === "/api/trade-diagnostics/history") {
      return await handleTradeDiagnosticsHistory(request, env, user);
    }

    if (request.method === "POST" && url.pathname === "/api/stocks/execution-analysis") {
      return await handleExecutionAnalysis(request, env);
    }

    return jsonResponse({ error: "NotFound", message: "Unknown route." }, 404, request, env);
  } catch (error) {
    return jsonResponse(
      {
        error: "WorkerFailure",
        message: error instanceof Error ? error.message : "Unknown worker error",
      },
      500,
      request,
      env,
    );
  }
}

export default {
  fetch: routeRequest,
};
