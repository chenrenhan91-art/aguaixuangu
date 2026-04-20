import { createClient } from "jsr:@supabase/supabase-js@2";

import { corsHeaders } from "../_shared/cors.ts";

type JsonRecord = Record<string, unknown>;

function isPlainObject(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function truncateText(value: string, maxLength = 240): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "";
  }
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}...` : normalized;
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function extractBearerToken(request: Request): string {
  const authorization = request.headers.get("Authorization") || request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() || "";
}

function parseJsonText(value: string): unknown {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return null;
  }
  try {
    return JSON.parse(normalized);
  } catch (_error) {
    return normalized;
  }
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  if (request.method !== "POST") {
    return jsonResponse(
      {
        error: "method_not_allowed",
        message: "Only POST is supported.",
      },
      405,
    );
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  const makeWebhookUrl = Deno.env.get("MAKE_EXECUTION_ANALYSIS_WEBHOOK_URL") || "";

  if (!supabaseUrl || !serviceRoleKey || !makeWebhookUrl) {
    return jsonResponse(
      {
        error: "misconfigured_runtime",
        message: "Missing Supabase or Make environment configuration.",
      },
      500,
    );
  }

  const accessToken = extractBearerToken(request);
  if (!accessToken) {
    return jsonResponse(
      {
        error: "missing_bearer_token",
        message: "Please sign in before requesting AI analysis.",
      },
      401,
    );
  }

  const supabaseAdmin = createClient(supabaseUrl, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });

  const {
    data: { user },
    error: userError,
  } = await supabaseAdmin.auth.getUser(accessToken);

  if (userError || !user) {
    return jsonResponse(
      {
        error: "invalid_bearer_token",
        message: "Your session is invalid or has expired.",
        detail: userError?.message || "",
      },
      401,
    );
  }

  if (!user.email_confirmed_at) {
    return jsonResponse(
      {
        error: "email_not_confirmed",
        message: "Please confirm your email before using AI analysis.",
      },
      403,
    );
  }

  const { data: inviteClaim, error: inviteClaimError } = await supabaseAdmin
    .from("invite_claims")
    .select("user_id, email, activated_at, revoked_at")
    .eq("user_id", user.id)
    .maybeSingle();

  if (inviteClaimError) {
    return jsonResponse(
      {
        error: "invite_claim_lookup_failed",
        message: "Failed to validate invite status.",
        detail: inviteClaimError.message,
      },
      500,
    );
  }

  if (!inviteClaim || inviteClaim.revoked_at) {
    return jsonResponse(
      {
        error: "invite_required",
        message: "Your account is not authorized to use AI analysis.",
      },
      403,
    );
  }

  let inviteActivatedAt = inviteClaim.activated_at || "";
  if (!inviteActivatedAt) {
    const activatedAt = new Date().toISOString();
    const { error: activateError } = await supabaseAdmin
      .from("invite_claims")
      .update({ activated_at: activatedAt })
      .eq("user_id", user.id)
      .is("revoked_at", null);

    if (activateError) {
      return jsonResponse(
        {
          error: "invite_activation_failed",
          message: "Failed to activate invite usage.",
          detail: activateError.message,
        },
        500,
      );
    }
    inviteActivatedAt = activatedAt;
  }

  let requestPayload: unknown;
  try {
    requestPayload = await request.json();
  } catch (_error) {
    return jsonResponse(
      {
        error: "invalid_json_body",
        message: "Request body must be valid JSON.",
      },
      400,
    );
  }

  if (!isPlainObject(requestPayload)) {
    return jsonResponse(
      {
        error: "invalid_request_body",
        message: "Request body must be a JSON object.",
      },
      400,
    );
  }

  const makePayload: JsonRecord = {
    ...requestPayload,
    user_id: user.id,
    email: user.email || inviteClaim.email || "",
    auth_context: {
      user_id: user.id,
      email: user.email || inviteClaim.email || "",
      email_confirmed_at: user.email_confirmed_at,
      invite_activated_at: inviteActivatedAt,
    },
  };

  try {
    const makeResponse = await fetch(makeWebhookUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(makePayload),
      signal: AbortSignal.timeout(20000),
    });

    const rawText = await makeResponse.text();
    const parsedAnalysis = parseJsonText(rawText);

    if (!makeResponse.ok) {
      return jsonResponse(
        {
          error: "make_upstream_error",
          message: "Make webhook returned a non-2xx response.",
          upstream_status: makeResponse.status,
          upstream_status_text: makeResponse.statusText,
          response_preview: truncateText(rawText),
        },
        502,
      );
    }

    return jsonResponse({
      status: "ok",
      analysis: parsedAnalysis,
      source: "supabase_function_make_proxy",
      authenticated_user: {
        id: user.id,
        email: user.email || inviteClaim.email || "",
        email_confirmed_at: user.email_confirmed_at,
        invite_activated_at: inviteActivatedAt,
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const isTimeout = /\btimeout\b/i.test(message) || /\babort\b/i.test(message);
    return jsonResponse(
      {
        error: isTimeout ? "make_upstream_timeout" : "make_upstream_request_failed",
        message: isTimeout ? "Timed out while waiting for Make webhook response." : "Failed to reach Make webhook.",
        detail: truncateText(message),
      },
      isTimeout ? 504 : 502,
    );
  }
});
