import json
from datetime import datetime
from pathlib import Path

from data_pipeline.config import load_config
from data_pipeline.renderers.preview_html import build_frontend_snapshot, render_preview_html
from data_pipeline.selection_engine import generate_daily_candidates


def run_generate_daily_candidates() -> dict[str, str]:
    config = load_config()
    raw_snapshot = generate_daily_candidates()
    snapshot = build_frontend_snapshot(raw_snapshot, config.project_root / "index.html")

    trade_date = snapshot["trade_date"]
    processed_dir = config.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    dated_output_path = processed_dir / f"daily_candidates_{trade_date}.json"
    latest_output_path = processed_dir / "daily_candidates_latest.json"

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    dated_output_path.write_text(payload, encoding="utf-8")
    latest_output_path.write_text(payload, encoding="utf-8")

    index_html_path = config.project_root / "index.html"
    render_preview_html(snapshot, index_html_path)

    return {
        "trade_date": trade_date,
        "json_output": str(latest_output_path),
        "dated_json_output": str(dated_output_path),
        "index_html": str(index_html_path),
        "candidate_count": str(len(snapshot["candidate_pool"])),
    }


if __name__ == "__main__":
    result = run_generate_daily_candidates()
    print(json.dumps(result, ensure_ascii=False, indent=2))
