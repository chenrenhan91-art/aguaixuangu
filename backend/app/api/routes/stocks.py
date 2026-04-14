from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from app.schemas.stock import AIRiskAnalysisResponse, StockDetailResponse
from app.services.ai_risk import regenerate_ai_risk_analysis
from app.services.stocks import get_stock_detail


router = APIRouter()


@router.post("/execution-analysis")
def execution_analysis(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or payload.get("detail", {}).get("symbol") or "").strip().upper()
    mode = payload.get("mode_id") or payload.get("mode")
    detail = payload.get("detail") or {}
    fallback = detail.get("ai_risk_analysis") or {
        "status": "fallback_rules",
        "model": None,
        "confidence": 0.52,
        "summary": "AI 执行分析暂时不可用，先按规则结构观察。",
        "highlights": [],
        "execution_plan": [],
        "next_step": "优先观察规则位与事件流是否继续强化。",
        "source": "backend-fallback",
    }
    if not symbol:
        raise HTTPException(status_code=400, detail="缺少 symbol 或 detail.symbol。")

    try:
        analysis = regenerate_ai_risk_analysis(symbol=symbol, mode=mode)
    except KeyError:
        analysis = fallback

    return {"analysis": analysis}


@router.get("/{symbol}", response_model=StockDetailResponse)
def stock_detail(symbol: str, mode: Optional[str] = Query(default=None)) -> StockDetailResponse:
    try:
        detail = get_stock_detail(symbol.upper(), mode=mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown strategy mode: {exc.args[0]}") from exc
    if detail is None:
        raise HTTPException(status_code=404, detail="Stock symbol not found in demo data.")
    return detail


@router.post("/{symbol}/ai-risk-analysis", response_model=AIRiskAnalysisResponse)
def regenerate_stock_ai_risk_analysis(
    symbol: str, mode: Optional[str] = Query(default=None)
) -> AIRiskAnalysisResponse:
    try:
        analysis = regenerate_ai_risk_analysis(symbol.upper(), mode=mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Stock or mode not found: {exc.args[0]}") from exc
    return AIRiskAnalysisResponse(**analysis)
