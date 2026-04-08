from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class MarketRegimeSnapshot:
    regime: str
    confidence: float
    suggested_exposure: float
    breadth_score: float
    northbound_score: float
    momentum_score: float
    updated_at: datetime


@dataclass
class SectorRanking:
    sector_code: str
    sector_name: str
    strength_score: float
    momentum_score: float
    capital_consensus_score: float
    heat_score: float


@dataclass
class CandidateSignal:
    symbol: str
    name: str
    industry: str
    rank: int
    base_score: float
    event_score: float
    risk_adjusted_score: float
    holding_window: str
    reasons: list[tuple[str, str]] = field(default_factory=list)
    event_tags: list[str] = field(default_factory=list)


@dataclass
class NewsEventRecord:
    event_id: str
    title: str
    publish_time: datetime
    source: str
    event_type: str
    sentiment: str
    impact_level: str
    summary: str


@dataclass
class StockResearchBrief:
    symbol: str
    name: str
    industry: str
    thesis: str
    market_context: str
    feature_scores: list[tuple[str, float, str]]
    recent_events: list[NewsEventRecord]
    risk_controls: list[str]


@dataclass
class EquityCurvePoint:
    trade_date: date
    equity: float
    drawdown: float


@dataclass
class TradeRecord:
    symbol: str
    name: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    pnl: float
    holding_days: int
