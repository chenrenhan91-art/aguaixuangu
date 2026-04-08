from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FeatureScore(BaseModel):
    name: str
    value: float
    description: str


class NewsEvent(BaseModel):
    event_id: str
    title: str
    publish_time: datetime
    source: str
    source_category: Optional[str] = None
    event_type: str
    sentiment: str
    impact_level: str
    summary: str
    link: Optional[str] = None


class RiskPlanResponse(BaseModel):
    price_basis: str
    reference_price: float
    stop_loss_price: float
    stop_loss_pct: float
    take_profit_price_1: float
    take_profit_pct_1: float
    take_profit_price_2: float
    take_profit_pct_2: float
    trailing_stop_price: float
    suggested_position_min: float
    suggested_position_max: float
    max_portfolio_risk: float
    risk_reward_ratio: float
    action_bias: str
    action_note: str
    analysis_method: str
    execution_notes: list[str]


class AIRiskAnalysisResponse(BaseModel):
    status: str
    model: Optional[str] = None
    confidence: float
    summary: str
    stance: Optional[str] = None
    setup_quality: Optional[str] = None
    key_signal: Optional[str] = None
    highlights: list[str]
    trigger_points: list[str] = []
    invalidation_points: list[str] = []
    execution_plan: list[str] = []
    next_step: str
    source: Optional[str] = None
    generated_at: Optional[datetime] = None


class StockDetailResponse(BaseModel):
    symbol: str
    name: str
    industry: str
    thesis: str
    market_context: str
    feature_scores: list[FeatureScore]
    recent_events: list[NewsEvent]
    risk_plan: Optional[RiskPlanResponse] = None
    ai_risk_analysis: Optional[AIRiskAnalysisResponse] = None
    risk_controls: list[str]
