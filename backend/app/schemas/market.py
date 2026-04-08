from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MarketSentimentAnalysisResponse(BaseModel):
    status: str
    sentiment_label: str
    sentiment_score: float = Field(ge=0, le=100)
    tone_key: Literal["ice", "fade", "repair", "rotation", "trend"]
    temperature_value: float = Field(ge=0, le=100)
    temperature_label: str
    summary: str
    action_bias: str
    preferred_setup: Optional[str] = None
    avoid_action: Optional[str] = None
    dominant_signal: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    watchouts: list[str] = Field(default_factory=list)
    playbook: list[str] = Field(default_factory=list)
    source: str
    model: Optional[str] = None
    generated_at: Optional[datetime] = None


class MarketRegimeResponse(BaseModel):
    regime: Literal["risk_on", "neutral", "risk_off"]
    confidence: float = Field(ge=0, le=1)
    suggested_exposure: float = Field(ge=0, le=1)
    breadth_score: float = Field(ge=0, le=100)
    northbound_score: float = Field(ge=0, le=100)
    momentum_score: float = Field(ge=0, le=100)
    updated_at: datetime
    ai_sentiment: Optional[MarketSentimentAnalysisResponse] = None


class SectorSnapshot(BaseModel):
    sector_code: str
    sector_name: str
    strength_score: float = Field(ge=0, le=100)
    momentum_score: float = Field(ge=0, le=100)
    capital_consensus_score: float = Field(ge=0, le=100)
    heat_score: float = Field(ge=0, le=100)


class TopSectorsResponse(BaseModel):
    items: list[SectorSnapshot]
    updated_at: datetime
