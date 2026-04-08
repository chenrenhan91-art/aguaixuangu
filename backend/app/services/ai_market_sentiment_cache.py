from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import get_settings


def _cache_path() -> Path:
    settings = get_settings()
    cache_dir = settings.data_dir / "processed"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "ai_market_sentiment_cache.json"


def load_ai_market_sentiment_cache() -> dict[str, Any]:
    path = _cache_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_cached_market_sentiment(trade_date: str) -> Optional[dict[str, Any]]:
    payload = load_ai_market_sentiment_cache()
    return payload.get(trade_date)


def save_cached_market_sentiment(trade_date: str, analysis: dict[str, Any]) -> None:
    payload = load_ai_market_sentiment_cache()
    cached = analysis.copy()
    cached["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload[trade_date] = cached
    _cache_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
