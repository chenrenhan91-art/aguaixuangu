from typing import Optional

from app.schemas.stock import (
    AIRiskAnalysisResponse,
    FeatureScore,
    NewsEvent,
    RiskPlanResponse,
    StockDetailResponse,
)
from app.services.ai_risk import get_effective_ai_risk_analysis
from app.services.mock_data import demo_stock_briefs
from app.services.snapshot_store import load_latest_selection_snapshot, resolve_snapshot_mode


def build_demo_risk_plan(reference_price: float) -> RiskPlanResponse:
    stop_loss_pct = 0.055
    take_profit_pct_1 = 0.11
    take_profit_pct_2 = 0.19
    position_min = 0.06
    position_max = 0.1
    return RiskPlanResponse(
        price_basis="最近收盘价",
        reference_price=reference_price,
        stop_loss_price=round(reference_price * (1 - stop_loss_pct), 2),
        stop_loss_pct=stop_loss_pct,
        take_profit_price_1=round(reference_price * (1 + take_profit_pct_1), 2),
        take_profit_pct_1=take_profit_pct_1,
        take_profit_price_2=round(reference_price * (1 + take_profit_pct_2), 2),
        take_profit_pct_2=take_profit_pct_2,
        trailing_stop_price=round(reference_price * 0.98, 2),
        suggested_position_min=position_min,
        suggested_position_max=position_max,
        max_portfolio_risk=round(position_max * stop_loss_pct, 4),
        risk_reward_ratio=2.0,
        action_bias="跟踪持有",
        action_note="演示数据环境下使用固定风控模板，真实数据模式会改为按个股波动自动测算。",
        analysis_method="demo_template",
        execution_notes=[
            "跌破止损线优先减仓，避免单笔交易回撤扩大。",
            "达到第一止盈位可先兑现部分利润，再观察趋势延续。",
            "剩余仓位根据趋势强弱决定是否继续持有，而不是一次性全部卖出。",
        ],
    )


def build_demo_ai_risk_analysis() -> AIRiskAnalysisResponse:
    return AIRiskAnalysisResponse(
        status="demo_stub_ready",
        model=None,
        confidence=0.68,
        summary="当前展示的是规则型风控解释占位，后续接入 AI 后可在此输出更细的止盈止损和仓位推演。",
        highlights=[
            "先用规则算出止损、止盈和仓位区间，再交给 AI 做自然语言解释会更稳。",
            "AI 适合补充情景分析，例如高开、低开、冲高回落时的应对。",
            "真正接入 AI 后，建议把模式、市场状态、波动率和事件摘要一起送入模型。",
        ],
        next_step="后续可将大模型输出接到 ai_risk_analysis 字段，无需再改前端结构。",
        source="demo",
    )


def get_stock_detail(symbol: str, mode: Optional[str] = None) -> Optional[StockDetailResponse]:
    snapshot = load_latest_selection_snapshot()
    if snapshot is not None:
        _, mode_payload = resolve_snapshot_mode(snapshot, requested_mode=mode)
        stock_details = mode_payload.get("stock_details", {})
        if symbol in stock_details:
            stock = stock_details[symbol]
            ai_risk_analysis = get_effective_ai_risk_analysis(
                symbol=symbol,
                mode=mode_payload.get("mode_id", mode or "balanced"),
                stock=stock,
            )
            return StockDetailResponse(
                symbol=stock["symbol"],
                name=stock["name"],
                industry=stock["industry"],
                thesis=stock["thesis"],
                market_context=stock["market_context"],
                feature_scores=[
                    FeatureScore(
                        name=item["name"],
                        value=item["value"],
                        description=item["description"],
                    )
                    for item in stock["feature_scores"]
                ],
                recent_events=[
                    NewsEvent(
                        event_id=item["event_id"],
                        title=item["title"],
                        publish_time=item["publish_time"],
                        source=item["source"],
                        source_category=item.get("source_category"),
                        event_type=item["event_type"],
                        sentiment=item["sentiment"],
                        impact_level=item["impact_level"],
                        summary=item["summary"],
                        link=item.get("link"),
                    )
                    for item in stock["recent_events"]
                ],
                risk_plan=(
                    RiskPlanResponse(**stock["risk_plan"])
                    if stock.get("risk_plan") is not None
                    else None
                ),
                ai_risk_analysis=AIRiskAnalysisResponse(**ai_risk_analysis),
                risk_controls=stock["risk_controls"],
            )

    stock = demo_stock_briefs().get(symbol)
    if stock is None:
        return None

    return StockDetailResponse(
        symbol=stock.symbol,
        name=stock.name,
        industry=stock.industry,
        thesis=stock.thesis,
        market_context=stock.market_context,
        feature_scores=[
            FeatureScore(name=name, value=value, description=description)
            for name, value, description in stock.feature_scores
        ],
        recent_events=[
            NewsEvent(
                event_id=event.event_id,
                title=event.title,
                publish_time=event.publish_time,
                source=event.source,
                source_category=getattr(event, "source_category", None),
                event_type=event.event_type,
                sentiment=event.sentiment,
                impact_level=event.impact_level,
                summary=event.summary,
                link=getattr(event, "link", None),
            )
            for event in stock.recent_events
        ],
        risk_plan=build_demo_risk_plan(reference_price=50.0),
        ai_risk_analysis=build_demo_ai_risk_analysis(),
        risk_controls=stock.risk_controls,
    )
