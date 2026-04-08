from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.services.ai_market_sentiment_cache import (
    get_cached_market_sentiment,
    save_cached_market_sentiment,
)
from app.services.gemini_client import GeminiClientError, call_gemini_market_sentiment_analysis
from app.services.snapshot_store import load_latest_selection_snapshot


SENTIMENT_DISPLAY_MAP: dict[str, dict[str, Any]] = {
    "冰点防守": {
        "tone_key": "ice",
        "temperature_label": "低温防守段",
        "score_range": (0.0, 20.0),
        "default_score": 18.0,
        "action_bias": "控仓观察",
        "playbook": [
            "只保留最强主线做观察，不主动扩大试错。",
            "把节奏放到最慢，优先等待共振修复而不是抢反弹。",
            "盘前只记录强承接方向，暂不做情绪化追价。",
        ],
    },
    "退潮试错": {
        "tone_key": "fade",
        "temperature_label": "低温试错段",
        "score_range": (21.0, 40.0),
        "default_score": 32.0,
        "action_bias": "控仓观察",
        "playbook": [
            "只做低位确认，不碰午后脉冲和尾盘抢筹。",
            "把出手次数压低到最少，优先看承接而不是看弹性。",
            "候选池只跟踪前排强势票，落后分支及时剔除。",
        ],
    },
    "弱修复": {
        "tone_key": "repair",
        "temperature_label": "中温修复段",
        "score_range": (41.0, 55.0),
        "default_score": 47.0,
        "action_bias": "控仓观察",
        "playbook": [
            "轻仓试错，优先有事件确认的前排标的。",
            "只做回踩确认或弱转强，不做无量抬升。",
            "保持机动仓位，不同时铺开多个方向。",
        ],
    },
    "轮动博弈": {
        "tone_key": "rotation",
        "temperature_label": "暖区轮动段",
        "score_range": (56.0, 75.0),
        "default_score": 69.0,
        "action_bias": "精选轮动",
        "playbook": [
            "围绕最强两条主线做切换，不要同时分散铺仓。",
            "优先看排序靠前且量价确认更完整的候选股。",
            "盘中若主线切换加快，要及时去弱留强。",
        ],
    },
    "主线强化": {
        "tone_key": "trend",
        "temperature_label": "高温主线段",
        "score_range": (76.0, 100.0),
        "default_score": 88.0,
        "action_bias": "顺势跟随",
        "playbook": [
            "优先顺势跟随核心主线，确认后再提高出手效率。",
            "把仓位集中在最强方向，避免逆势抄底边缘票。",
            "高位加速只做强者，不参与后排补涨。",
        ],
    },
}


def _normalize_sentiment_label(raw_label: Any) -> str:
    label = str(raw_label or "").strip()
    if label in SENTIMENT_DISPLAY_MAP:
        return label
    return "轮动博弈"


def _normalize_sentiment_score(label: str, raw_score: Any) -> float:
    minimum, maximum = SENTIMENT_DISPLAY_MAP[label]["score_range"]
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = float(SENTIMENT_DISPLAY_MAP[label]["default_score"])
    return round(max(minimum, min(score, maximum)), 1)


def _attach_display_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    label = _normalize_sentiment_label(payload.get("sentiment_label"))
    display_meta = SENTIMENT_DISPLAY_MAP[label]
    enriched = dict(payload)
    enriched["sentiment_label"] = label
    enriched["sentiment_score"] = _normalize_sentiment_score(label, payload.get("sentiment_score"))
    enriched["tone_key"] = display_meta["tone_key"]
    enriched["temperature_value"] = enriched["sentiment_score"]
    enriched["temperature_label"] = display_meta["temperature_label"]
    enriched["action_bias"] = display_meta["action_bias"]
    enriched["playbook"] = list(display_meta["playbook"])
    enriched["tags"] = list(payload.get("tags") or [])[:3]
    enriched["watchouts"] = list(payload.get("watchouts") or [])[:2]
    return enriched


def _fallback_sentiment_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    market = snapshot.get("market_regime", {})
    breadth = float(market.get("breadth_score", 50.0))
    momentum = float(market.get("momentum_score", 50.0))
    northbound = float(market.get("northbound_score", 50.0))
    top_sectors = snapshot.get("top_sectors", [])[:3]
    sector_names = [item.get("sector_name", "") for item in top_sectors if item.get("sector_name")]
    average_heat = (
        sum(float(item.get("heat_score", 0.0)) for item in top_sectors) / len(top_sectors)
        if top_sectors
        else 50.0
    )

    if breadth >= 94 and momentum >= 90 and average_heat >= 84:
        label = "主线强化"
        score = 88.0
        action_bias = "顺势跟随"
        summary = "主线强化明显，盘前更适合围绕强势行业做确认后的顺势跟随。"
        tags = ["主线集中", "强者恒强", "去弱留强"]
        watchouts = ["高位加速段不宜盲目追最后一棒。", "若核心股午后放量回落，需提防强转分歧。"]
    elif breadth >= 68 and momentum >= 66:
        label = "轮动博弈"
        score = 69.0
        action_bias = "精选轮动"
        summary = "资金更像在板块间快速轮动，盘前只适合做主线精选，不宜同时铺太多方向。"
        tags = ["轮动偏快", "去弱留强", "不宜分散"]
        watchouts = ["低位补涨与高位龙头可能分化。", "候选池里更要强调排序和确认。"]
    elif breadth >= 50:
        label = "弱修复"
        score = 47.0
        action_bias = "控仓观察"
        summary = "情绪有修复迹象但力度仍弱，盘前更适合小仓位观察，不宜强行提速。"
        tags = ["修复偏弱", "试错有限", "节奏放慢"]
        watchouts = ["热点持续性不够时，追高性价比较低。", "若北向继续走弱，修复可能中断。"]
    elif breadth >= 34:
        label = "退潮试错"
        score = 32.0
        action_bias = "控仓观察"
        summary = "市场更接近退潮试错阶段，盘前应少做追价，优先等待更清晰的共振信号。"
        tags = ["退潮期", "追高降速", "先看承接"]
        watchouts = ["任何脉冲都需要防兑现回落。", "低胜率阶段不适合扩大试错次数。"]
    else:
        label = "冰点防守"
        score = 18.0
        action_bias = "控仓观察"
        summary = "市场情绪接近冰点防守，盘前重点是保护净值，不宜主动放大试错。"
        tags = ["防守优先", "等待修复", "不追脉冲"]
        watchouts = ["先等主线与情绪一起企稳。", "无共振的反弹更适合看，不适合追。"]

    if northbound < 45 and label in {"主线强化", "轮动博弈"}:
        watchouts.insert(0, "北向承接偏弱，说明情绪虽暖但仍需要观察增量资金是否跟上。")
    if sector_names and "主线集中" not in tags:
        tags = [sector_names[0], *tags][:3]

    return _attach_display_metadata(
        {
        "status": "fallback_rules",
        "sentiment_label": label,
        "sentiment_score": round(score, 1),
        "summary": summary,
        "action_bias": action_bias,
        "preferred_setup": "优先盯最强主线前排。",
        "avoid_action": "不要追后排与无承接脉冲。",
        "dominant_signal": "以广度、动量和主线集中度为主。",
        "tags": tags[:3],
        "watchouts": watchouts[:2],
        "source": "rules",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def build_market_sentiment_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    market = snapshot.get("market_regime", {})
    top_sectors = snapshot.get("top_sectors", [])[:5]
    market_news = snapshot.get("market_news", [])[:5]
    return {
        "trade_date": snapshot.get("trade_date"),
        "strategy_version": snapshot.get("strategy_version"),
        "market_regime": market,
        "top_sectors": [
            {
                "sector_name": item.get("sector_name"),
                "strength_score": item.get("strength_score"),
                "momentum_score": item.get("momentum_score"),
                "heat_score": item.get("heat_score"),
            }
            for item in top_sectors
        ],
        "market_news": [
            {
                "title": item.get("title"),
                "summary": item.get("summary"),
                "publish_time": item.get("publish_time"),
            }
            for item in market_news
        ],
        "selection_meta": snapshot.get("selection_meta", {}),
    }


def fuse_market_sentiment(ai_result: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    confidence_like_score = float(ai_result.get("sentiment_score", fallback.get("sentiment_score", 50.0)))
    confidence_like_score = max(0.0, min(100.0, confidence_like_score))
    return _attach_display_metadata(
        {
        "status": "ai_live",
        "sentiment_label": ai_result.get("sentiment_label") or fallback["sentiment_label"],
        "sentiment_score": round(confidence_like_score, 1),
        "summary": ai_result.get("summary") or fallback["summary"],
        "action_bias": ai_result.get("action_bias") or fallback["action_bias"],
        "preferred_setup": ai_result.get("preferred_setup") or fallback.get("preferred_setup"),
        "avoid_action": ai_result.get("avoid_action") or fallback.get("avoid_action"),
        "dominant_signal": ai_result.get("dominant_signal") or fallback.get("dominant_signal"),
        "tags": list(ai_result.get("tags") or fallback["tags"])[:3],
        "watchouts": list(ai_result.get("watchouts") or fallback["watchouts"])[:2],
        "source": "gemini",
        "model": ai_result.get("model"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def get_effective_market_sentiment(snapshot: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    effective_snapshot = snapshot or load_latest_selection_snapshot()
    if effective_snapshot is None:
        return _attach_display_metadata(
            {
            "status": "fallback_rules",
            "sentiment_label": "轮动博弈",
            "sentiment_score": 55.0,
            "summary": "当前缺少最新快照，先按轮动博弈处理，只做更靠前的主线排序。",
            "action_bias": "控仓观察",
            "tags": ["先看主线", "排序优先", "节奏放慢"],
            "watchouts": ["先围绕排序靠前的主线方向做观察。"],
            "source": "rules",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    trade_date = effective_snapshot.get("trade_date")
    if trade_date:
        cached = get_cached_market_sentiment(trade_date)
        if cached is not None:
            return _attach_display_metadata(cached)

    fallback = _fallback_sentiment_from_snapshot(effective_snapshot)
    context = build_market_sentiment_context(effective_snapshot)
    try:
        ai_result = call_gemini_market_sentiment_analysis(context)
        fused = fuse_market_sentiment(ai_result, fallback)
    except GeminiClientError:
        fused = fallback

    if trade_date:
        save_cached_market_sentiment(trade_date, fused)
    return fused


def regenerate_market_sentiment() -> dict[str, Any]:
    snapshot = load_latest_selection_snapshot()
    if snapshot is None:
        raise KeyError("snapshot")
    fallback = _fallback_sentiment_from_snapshot(snapshot)
    context = build_market_sentiment_context(snapshot)
    try:
        ai_result = call_gemini_market_sentiment_analysis(context)
        fused = fuse_market_sentiment(ai_result, fallback)
    except GeminiClientError:
        fused = fallback

    trade_date = snapshot.get("trade_date")
    if trade_date:
        save_cached_market_sentiment(trade_date, fused)
    return fused
