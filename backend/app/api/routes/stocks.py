from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.stock import AIRiskAnalysisResponse, StockDetailResponse
from app.services.ai_risk import regenerate_ai_risk_analysis
from app.services.stocks import get_stock_detail


router = APIRouter()


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
