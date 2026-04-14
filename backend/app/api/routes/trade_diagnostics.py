from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile

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
from app.services.gemini_client import GeminiClientError, call_gemini_trade_diagnostics_analysis


router = APIRouter()


def _merge_trade_diagnostics(local_diagnostics: dict[str, Any], ai_result: dict[str, Any]) -> dict[str, Any]:
    return {
        **local_diagnostics,
        "status": "ai_live",
        "ai_analysis": {
            "status": "ai_live",
            "model": ai_result.get("model"),
            "confidence": float(ai_result.get("confidence", 0.68)),
            "summary": ai_result.get("summary") or local_diagnostics.get("ai_analysis", {}).get("summary") or "--",
            "trader_profile": ai_result.get("trader_profile") or local_diagnostics.get("style_profile", {}).get("summary") or "--",
            "strengths": list(ai_result.get("strengths") or []),
            "weaknesses": list(ai_result.get("weaknesses") or []),
            "behavior_tags": list(ai_result.get("behavior_tags") or []),
            "adjustments": list(ai_result.get("adjustments") or []),
            "next_cycle_plan": list(ai_result.get("next_cycle_plan") or []),
            "source": "backend-gemini",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


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


@router.post("/analyze")
def trade_diagnostics_analyze(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    local_diagnostics = payload.get("local_diagnostics") or payload.get("localDiagnostics")
    if not isinstance(local_diagnostics, dict):
        raise HTTPException(status_code=400, detail="缺少 local_diagnostics。")

    diagnostics = local_diagnostics
    try:
        ai_result = call_gemini_trade_diagnostics_analysis(local_diagnostics)
        diagnostics = _merge_trade_diagnostics(local_diagnostics, ai_result)
    except GeminiClientError:
        diagnostics = {
            **local_diagnostics,
            "ai_analysis": local_diagnostics.get("ai_analysis"),
        }

    return {"diagnostics": diagnostics}


@router.post("/history")
def trade_diagnostics_history() -> dict[str, Any]:
    diagnostics = get_trade_diagnostics().model_dump(mode="json")
    return {"diagnostics": diagnostics}
