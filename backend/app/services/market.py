from app.schemas.market import MarketRegimeResponse, MarketSentimentAnalysisResponse
from app.services.ai_market_sentiment import (
    get_effective_market_sentiment,
    regenerate_market_sentiment,
)
from app.services.mock_data import demo_market_regime
from app.services.snapshot_store import load_latest_selection_snapshot


def get_market_regime() -> MarketRegimeResponse:
    snapshot = load_latest_selection_snapshot()
    if snapshot is not None:
        regime = snapshot["market_regime"]
        ai_sentiment = get_effective_market_sentiment(snapshot)
        return MarketRegimeResponse(
            regime=regime["regime"],
            confidence=regime["confidence"],
            suggested_exposure=regime["suggested_exposure"],
            breadth_score=regime["breadth_score"],
            northbound_score=regime["northbound_score"],
            momentum_score=regime["momentum_score"],
            updated_at=regime["updated_at"],
            ai_sentiment=MarketSentimentAnalysisResponse(**ai_sentiment),
        )

    snapshot = demo_market_regime()
    ai_sentiment = get_effective_market_sentiment(None)
    return MarketRegimeResponse(
        regime=snapshot.regime,
        confidence=snapshot.confidence,
        suggested_exposure=snapshot.suggested_exposure,
        breadth_score=snapshot.breadth_score,
        northbound_score=snapshot.northbound_score,
        momentum_score=snapshot.momentum_score,
        updated_at=snapshot.updated_at,
        ai_sentiment=MarketSentimentAnalysisResponse(**ai_sentiment),
    )


def regenerate_market_sentiment_analysis() -> MarketSentimentAnalysisResponse:
    sentiment = regenerate_market_sentiment()
    return MarketSentimentAnalysisResponse(**sentiment)
