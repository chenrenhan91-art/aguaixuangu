from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.signals import DailySignalsResponse
from app.services.signals import get_daily_signals


router = APIRouter()


@router.get("/daily", response_model=DailySignalsResponse)
def daily_signals(
    limit: int = Query(default=10, ge=1, le=50),
    mode: Optional[str] = Query(default=None),
) -> DailySignalsResponse:
    try:
        return get_daily_signals(limit=limit, mode=mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown strategy mode: {exc.args[0]}") from exc
