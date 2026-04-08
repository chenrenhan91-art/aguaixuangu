from datetime import date
from typing import Optional

from app.schemas.signals import (
    DailySignal,
    DailySignalsResponse,
    SignalReason,
    StrategyModeOption,
)
from app.services.mock_data import demo_market_regime, demo_signals
from app.services.snapshot_store import (
    list_snapshot_modes,
    load_latest_selection_snapshot,
    resolve_snapshot_mode,
)


def get_daily_signals(limit: int = 10, mode: Optional[str] = None) -> DailySignalsResponse:
    snapshot = load_latest_selection_snapshot()
    if snapshot is not None:
        selected_mode, mode_payload = resolve_snapshot_mode(snapshot, requested_mode=mode)
        items = mode_payload["items"][:limit]
        return DailySignalsResponse(
            trade_date=snapshot["trade_date"],
            strategy_version=snapshot["strategy_version"],
            market_regime=snapshot["market_regime"]["regime"],
            selected_mode=selected_mode,
            selected_mode_name=mode_payload.get("display_name", selected_mode),
            mode_description=mode_payload.get("description", ""),
            available_modes=[
                StrategyModeOption(
                    mode_id=item["mode_id"],
                    display_name=item["display_name"],
                    description=item["description"],
                    holding_window=item["holding_window"],
                )
                for item in list_snapshot_modes(snapshot)
            ],
            items=[
                DailySignal(
                    symbol=item["symbol"],
                    name=item["name"],
                    industry=item["industry"],
                    rank=item["rank"],
                    base_score=item["base_score"],
                    event_score=item["event_score"],
                    risk_adjusted_score=item["risk_adjusted_score"],
                    holding_window=item["holding_window"],
                    reasons=[
                        SignalReason(label=reason["label"], detail=reason["detail"])
                        for reason in item["reasons"]
                    ],
                    event_tags=item["event_tags"],
                )
                for item in items
            ],
        )

    signals = demo_signals()[:limit]
    market = demo_market_regime()
    return DailySignalsResponse(
        trade_date=date.today(),
        strategy_version="v2-mvp-baseline",
        market_regime=market.regime,
        selected_mode="balanced",
        selected_mode_name="综合研判",
        mode_description="默认综合模式。",
        available_modes=[
            StrategyModeOption(
                mode_id="balanced",
                display_name="综合研判",
                description="默认综合模式。",
                holding_window="3-5D",
            )
        ],
        items=[
            DailySignal(
                symbol=signal.symbol,
                name=signal.name,
                industry=signal.industry,
                rank=signal.rank,
                base_score=signal.base_score,
                event_score=signal.event_score,
                risk_adjusted_score=signal.risk_adjusted_score,
                holding_window=signal.holding_window,
                reasons=[
                    SignalReason(label=label, detail=detail)
                    for label, detail in signal.reasons
                ],
                event_tags=signal.event_tags,
            )
            for signal in signals
        ],
    )
