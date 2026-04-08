from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.schemas.trade_diagnostics import (
    ImportProfilesResponse,
    TradeDiagnosticsAIResponse,
    TradeDiagnosticsResponse,
    TradeImportResponse,
)
from app.services.trade_diagnostics import (
    export_trade_schema_blueprint,
    get_import_profiles,
    get_trade_diagnostics,
    import_trade_file,
    regenerate_trade_diagnostics_ai_analysis,
)


router = APIRouter()


@router.get("/profiles", response_model=ImportProfilesResponse)
def import_profiles() -> ImportProfilesResponse:
    return get_import_profiles()


@router.get("/summary", response_model=TradeDiagnosticsResponse)
def trade_diagnostics_summary() -> TradeDiagnosticsResponse:
    return get_trade_diagnostics()


@router.post("/ai-analysis", response_model=TradeDiagnosticsAIResponse)
def trade_diagnostics_ai_analysis(
    batch_id: Optional[str] = None,
) -> TradeDiagnosticsAIResponse:
    return TradeDiagnosticsAIResponse(**regenerate_trade_diagnostics_ai_analysis(batch_id=batch_id))


@router.get("/schema")
def trade_schema() -> dict:
    return export_trade_schema_blueprint()


@router.post("/import", response_model=TradeImportResponse)
async def import_trade_statement(
    profile_id: str = Form(...),
    file: UploadFile = File(...),
) -> TradeImportResponse:
    return await import_trade_file(upload=file, profile_id=profile_id)
