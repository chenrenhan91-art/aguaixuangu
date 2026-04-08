import json
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.adapters.market import DemoMarketDataAdapter
from data_pipeline.adapters.news import DemoNewsAdapter
from data_pipeline.config import load_config
from data_pipeline.validators.quality import summarize_row_count, validate_required_fields


def run_daily_refresh() -> dict[str, object]:
    config = load_config()
    market_rows = DemoMarketDataAdapter(
        symbols=["000977.SZ", "603019.SH", "300308.SZ"]
    ).fetch()
    news_rows = DemoNewsAdapter().fetch()

    market_errors = validate_required_fields(
        market_rows,
        ["trade_date", "symbol", "open", "high", "low", "close", "amount"],
    )
    news_errors = validate_required_fields(
        news_rows,
        ["event_id", "publish_time", "source", "title", "event_type", "summary"],
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_rows": market_rows,
        "news_rows": news_rows,
        "quality_checks": [
            summarize_row_count(market_rows, "market_rows"),
            summarize_row_count(news_rows, "news_rows"),
        ],
        "errors": {
            "market": market_errors,
            "news": news_errors,
        },
    }

    output_path = config.raw_data_dir / f"daily_refresh_{datetime.now().date().isoformat()}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "output_path": str(output_path),
        "market_rows": len(market_rows),
        "news_rows": len(news_rows),
        "market_errors": len(market_errors),
        "news_errors": len(news_errors),
    }


if __name__ == "__main__":
    result = run_daily_refresh()
    print(json.dumps(result, ensure_ascii=False, indent=2))

