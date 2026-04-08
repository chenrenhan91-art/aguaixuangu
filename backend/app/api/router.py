from fastapi import APIRouter

from app.api.routes import health, market, sectors, signals, stocks, trade_diagnostics


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(sectors.router, prefix="/sectors", tags=["sectors"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(
    trade_diagnostics.router,
    prefix="/trade-diagnostics",
    tags=["trade-diagnostics"],
)
