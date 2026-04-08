import json
from datetime import datetime
from pathlib import Path
from shutil import copyfile

from data_pipeline.config import load_config
from data_pipeline.renderers.preview_html import render_preview_html
from data_pipeline.selection_engine import generate_daily_candidates


def run_generate_daily_candidates() -> dict[str, str]:
    config = load_config()
    snapshot = generate_daily_candidates()

    trade_date = snapshot["trade_date"]
    processed_dir = config.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    dated_output_path = processed_dir / f"daily_candidates_{trade_date}.json"
    latest_output_path = processed_dir / "daily_candidates_latest.json"

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    dated_output_path.write_text(payload, encoding="utf-8")
    latest_output_path.write_text(payload, encoding="utf-8")

    preview_path = config.project_root / "A股AI选股工具预览.html"
    primary_html_path = config.project_root / "A股AI选股工具.html"
    render_preview_html(snapshot, primary_html_path)
    copyfile(primary_html_path, preview_path)

    return {
        "trade_date": trade_date,
        "json_output": str(latest_output_path),
        "dated_json_output": str(dated_output_path),
        "primary_html": str(primary_html_path),
        "preview_html": str(preview_path),
        "candidate_count": str(len(snapshot["candidate_pool"])),
    }


if __name__ == "__main__":
    result = run_generate_daily_candidates()
    print(json.dumps(result, ensure_ascii=False, indent=2))
