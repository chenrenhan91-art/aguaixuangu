from datetime import date

from pydantic import BaseModel, Field


class SignalReason(BaseModel):
    label: str
    detail: str


class StrategyModeOption(BaseModel):
    mode_id: str
    display_name: str
    description: str
    holding_window: str


class DailySignal(BaseModel):
    symbol: str
    name: str
    industry: str
    rank: int = Field(ge=1)
    base_score: float = Field(ge=0, le=100)
    event_score: float = Field(ge=0, le=100)
    risk_adjusted_score: float = Field(ge=0, le=100)
    holding_window: str
    reasons: list[SignalReason]
    event_tags: list[str] = Field(default_factory=list)


class DailySignalsResponse(BaseModel):
    trade_date: date
    strategy_version: str
    market_regime: str
    selected_mode: str
    selected_mode_name: str
    mode_description: str
    available_modes: list[StrategyModeOption] = Field(default_factory=list)
    items: list[DailySignal]
