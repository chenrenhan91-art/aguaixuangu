from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ImportProfile(BaseModel):
    profile_id: str
    display_name: str
    broker: str
    supported_extensions: list[str] = Field(default_factory=list)
    recommended_format: str
    description: str
    export_steps: list[str] = Field(default_factory=list)


class StandardFieldDefinition(BaseModel):
    field_name: str
    display_name: str
    required: bool
    description: str


class ImportProfilesResponse(BaseModel):
    profiles: list[ImportProfile] = Field(default_factory=list)
    standard_fields: list[StandardFieldDefinition] = Field(default_factory=list)


class ImportBatchSummary(BaseModel):
    batch_id: str
    imported_at: datetime
    broker: str
    source_type: str
    filename: str
    detected_format: str
    row_count: int
    imported_count: int
    ignored_count: int
    symbol_count: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class TradeImportResponse(BaseModel):
    batch: ImportBatchSummary
    message: str


class MetricCard(BaseModel):
    label: str
    value: str
    detail: str


class TradeStyleProfile(BaseModel):
    style_id: str
    display_name: str
    confidence: float = Field(ge=0, le=1)
    summary: str
    traits: list[str] = Field(default_factory=list)


class DiagnosticInsight(BaseModel):
    title: str
    detail: str
    severity: str


class TradeDiagnosticsAIResponse(BaseModel):
    status: str
    model: Optional[str] = None
    confidence: float = Field(ge=0, le=1)
    summary: str
    trader_profile: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    behavior_tags: list[str] = Field(default_factory=list)
    adjustments: list[str] = Field(default_factory=list)
    next_cycle_plan: list[str] = Field(default_factory=list)
    source: Optional[str] = None
    generated_at: Optional[datetime] = None


class TradeDiagnosticsResponse(BaseModel):
    status: str
    account_label: str
    coverage_text: str
    latest_batch: Optional[ImportBatchSummary] = None
    summary_metrics: list[MetricCard] = Field(default_factory=list)
    style_profile: TradeStyleProfile
    win_loss_comparison: list[MetricCard] = Field(default_factory=list)
    error_patterns: list[DiagnosticInsight] = Field(default_factory=list)
    effective_patterns: list[DiagnosticInsight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    recent_batches: list[ImportBatchSummary] = Field(default_factory=list)
    ai_analysis: Optional[TradeDiagnosticsAIResponse] = None
