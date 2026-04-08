from fastapi import APIRouter

from app.schemas.market import MarketRegimeResponse, MarketSentimentAnalysisResponse
from app.services.market import get_market_regime, regenerate_market_sentiment_analysis


router = APIRouter()


@router.get("/regime", response_model=MarketRegimeResponse)
def market_regime() -> MarketRegimeResponse:
    return get_market_regime()


@router.post("/sentiment-analysis", response_model=MarketSentimentAnalysisResponse)
def market_sentiment_analysis() -> MarketSentimentAnalysisResponse:
    return regenerate_market_sentiment_analysis()
