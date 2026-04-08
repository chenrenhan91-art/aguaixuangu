from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import get_settings
from app.services.ai_risk_cache import get_cached_ai_risk_analysis, save_cached_ai_risk_analysis
from app.services.gemini_client import GeminiClientError, call_gemini_risk_analysis
from app.services.snapshot_store import load_latest_selection_snapshot, resolve_snapshot_mode


def _fallback_ai_analysis(stock: dict[str, Any]) -> dict[str, Any]:
    ai_analysis = stock.get("ai_risk_analysis", {}) or {}
    fallback = ai_analysis.copy()
    fallback.setdefault("status", "rule_stub_ready")
    fallback.setdefault("model", None)
    fallback.setdefault("confidence", 0.6)
    fallback.setdefault("summary", "当前先按结构化规则观察，不做额外主观放宽。")
    fallback.setdefault("stance", "跟踪")
    fallback.setdefault("setup_quality", "B")
    fallback.setdefault("key_signal", "先看规则位附近的承接与事件催化是否继续强化。")
    fallback.setdefault("highlights", ["当前为规则型结论，适合作为基础执行参考。"])
    fallback.setdefault("trigger_points", ["价格与事件共振继续强化。"])
    fallback.setdefault("invalidation_points", ["关键支撑失守后未见快速修复。"])
    fallback.setdefault("execution_plan", ["先看确认，再决定是否执行。"])
    fallback.setdefault("next_step", "优先观察规则位附近的量价反馈。")
    fallback.setdefault("source", "rules")
    fallback.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    return fallback


def build_ai_request_context(snapshot: dict[str, Any], mode_payload: dict[str, Any], stock: dict[str, Any]) -> dict[str, Any]:
    candidate_map = {item["symbol"]: item for item in mode_payload.get("items", [])}
    candidate = candidate_map.get(stock["symbol"], {})
    raw_risk_plan = stock.get("risk_plan", {}) or {}
    rule_risk_plan = {
        key: value
        for key, value in raw_risk_plan.items()
        if key
        not in {
            "suggested_position_min",
            "suggested_position_max",
            "max_portfolio_risk",
            "risk_reward_ratio",
        }
    }
    return {
        "trade_date": snapshot.get("trade_date"),
        "strategy_version": snapshot.get("strategy_version"),
        "market_regime": snapshot.get("market_regime", {}),
        "selected_mode": {
            "mode_id": mode_payload.get("mode_id"),
            "display_name": mode_payload.get("display_name"),
            "description": mode_payload.get("description"),
        },
        "stock": {
            "symbol": stock.get("symbol"),
            "name": stock.get("name"),
            "industry": stock.get("industry"),
            "thesis": stock.get("thesis"),
            "market_context": stock.get("market_context"),
            "feature_scores": stock.get("feature_scores", []),
            "recent_events": stock.get("recent_events", []),
            "rule_risk_plan": rule_risk_plan,
            "candidate_reasons": candidate.get("reasons", []),
        },
    }


def fuse_rule_and_ai_analysis(
    stock: dict[str, Any], ai_result: dict[str, Any], fallback_analysis: dict[str, Any]
) -> dict[str, Any]:
    risk_plan = stock.get("risk_plan", {})
    summary = ai_result.get("summary") or fallback_analysis.get("summary")
    highlights = list(ai_result.get("highlights") or fallback_analysis.get("highlights") or [])
    risk_bias = str(ai_result.get("risk_bias", "keep")).lower()
    trigger_points = list(ai_result.get("trigger_points") or fallback_analysis.get("trigger_points") or [])
    invalidation_points = list(
        ai_result.get("invalidation_points") or fallback_analysis.get("invalidation_points") or []
    )
    execution_plan = list(ai_result.get("execution_plan") or fallback_analysis.get("execution_plan") or [])
    if risk_bias == "tighten":
        highlights.insert(
            0,
            f"纪律偏紧，先尊重规则止损位 {risk_plan.get('stop_loss_price', '--')} 元。",
        )
    else:
        highlights.insert(
            0,
            f"优先围绕 {risk_plan.get('stop_loss_price', '--')} / {risk_plan.get('take_profit_price_1', '--')} / "
            f"{risk_plan.get('take_profit_price_2', '--')} 三个规则位执行。",
        )

    confidence = float(ai_result.get("confidence", fallback_analysis.get("confidence", 0.68)))
    confidence = max(0.0, min(1.0, confidence))
    if not trigger_points:
        trigger_points = [f"若价格围绕 {risk_plan.get('reference_price', '--')} 元附近承接稳定，再继续跟踪。"]
    if not invalidation_points:
        invalidation_points = [f"若跌破 {risk_plan.get('stop_loss_price', '--')} 元后仍无修复，先取消执行想法。"]
    if not execution_plan:
        execution_plan = [
            "先看事件与量价是否同步强化。",
            "只在确认信号出现后执行，不预判抢跑。",
        ]
    return {
        "status": "ai_live",
        "model": ai_result.get("model") or get_settings().gemini_model,
        "confidence": round(confidence, 2),
        "summary": summary,
        "stance": ai_result.get("stance") or fallback_analysis.get("stance"),
        "setup_quality": ai_result.get("setup_quality") or fallback_analysis.get("setup_quality"),
        "key_signal": ai_result.get("key_signal") or fallback_analysis.get("key_signal"),
        "highlights": highlights[:4],
        "trigger_points": trigger_points[:3],
        "invalidation_points": invalidation_points[:3],
        "execution_plan": execution_plan[:4],
        "next_step": ai_result.get("next_step") or fallback_analysis.get("next_step"),
        "source": "gemini",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_effective_ai_risk_analysis(symbol: str, mode: str, stock: dict[str, Any]) -> dict[str, Any]:
    cached = get_cached_ai_risk_analysis(symbol, mode)
    if cached is not None:
        return cached
    return _fallback_ai_analysis(stock)


def regenerate_ai_risk_analysis(symbol: str, mode: Optional[str]) -> dict[str, Any]:
    snapshot = load_latest_selection_snapshot()
    if snapshot is None:
        raise KeyError("snapshot")

    selected_mode, mode_payload = resolve_snapshot_mode(snapshot, requested_mode=mode)
    stock = mode_payload.get("stock_details", {}).get(symbol)
    if stock is None:
        raise KeyError(symbol)

    fallback_analysis = _fallback_ai_analysis(stock)
    context = build_ai_request_context(snapshot, mode_payload, stock)
    try:
        ai_result = call_gemini_risk_analysis(context)
        fused = fuse_rule_and_ai_analysis(stock, ai_result, fallback_analysis)
    except GeminiClientError as exc:
        fused = fallback_analysis
        fused["status"] = "ai_error"
        fused["next_step"] = str(exc)

    save_cached_ai_risk_analysis(symbol, selected_mode, fused)
    return fused
