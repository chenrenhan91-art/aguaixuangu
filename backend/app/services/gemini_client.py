from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.core.config import get_settings
from app.prompts.market_sentiment_prompt import (
    MARKET_SENTIMENT_PROMPT_VERSION,
    build_market_sentiment_system_instruction,
    build_market_sentiment_user_prompt,
)
from app.prompts.risk_analysis_prompt import (
    PROMPT_TEMPLATE_VERSION,
    build_risk_analysis_system_instruction,
    build_risk_analysis_user_prompt,
)
from app.prompts.trade_diagnostics_prompt import (
    TRADE_DIAGNOSTICS_PROMPT_VERSION,
    build_trade_diagnostics_system_instruction,
    build_trade_diagnostics_user_prompt,
)


class GeminiClientError(RuntimeError):
    pass


def _call_gemini_json(system_instruction: str, user_prompt: str, temperature: float = 0.25) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiClientError("Gemini API key is not configured.")

    payload = {
        "systemInstruction": {
            "parts": [
                {
                    "text": system_instruction,
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": user_prompt,
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "topP": 0.9,
            "responseMimeType": "application/json",
        },
    }

    req = request.Request(
        url=f"{settings.gemini_api_base}/models/{settings.gemini_model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=25) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="ignore")
        raise GeminiClientError(f"Gemini HTTP error {exc.code}: {message}") from exc
    except Exception as exc:
        raise GeminiClientError(f"Gemini request failed: {exc}") from exc

    candidates = response_payload.get("candidates", [])
    if not candidates:
        raise GeminiClientError("Gemini response contains no candidates.")

    text_parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in text_parts if isinstance(part, dict)).strip()
    if not text:
        raise GeminiClientError("Gemini response is empty.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f"Gemini returned non-JSON content: {text}") from exc


def call_gemini_risk_analysis(context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    parsed = _call_gemini_json(
        system_instruction=build_risk_analysis_system_instruction(),
        user_prompt=build_risk_analysis_user_prompt(context),
        temperature=0.25,
    )
    parsed["model"] = settings.gemini_model
    parsed["prompt_template_version"] = PROMPT_TEMPLATE_VERSION
    return parsed


def call_gemini_market_sentiment_analysis(context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    parsed = _call_gemini_json(
        system_instruction=build_market_sentiment_system_instruction(),
        user_prompt=build_market_sentiment_user_prompt(context),
        temperature=0.2,
    )
    parsed["model"] = settings.gemini_model
    parsed["prompt_template_version"] = MARKET_SENTIMENT_PROMPT_VERSION
    return parsed


def call_gemini_trade_diagnostics_analysis(context: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    parsed = _call_gemini_json(
        system_instruction=build_trade_diagnostics_system_instruction(),
        user_prompt=build_trade_diagnostics_user_prompt(context),
        temperature=0.2,
    )
    parsed["model"] = settings.gemini_model
    parsed["prompt_template_version"] = TRADE_DIAGNOSTICS_PROMPT_VERSION
    return parsed
