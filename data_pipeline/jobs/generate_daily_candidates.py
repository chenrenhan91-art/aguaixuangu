import json
import os

from data_pipeline.config import load_config
from data_pipeline.selection_engine import generate_daily_candidates


def _validate_snapshot(snapshot: dict) -> None:
    candidate_pool = snapshot.get("candidate_pool")
    strategy_modes = snapshot.get("strategy_modes")
    default_mode = snapshot.get("default_mode")

    if not isinstance(candidate_pool, list) or not candidate_pool:
        raise RuntimeError("Snapshot candidate_pool is empty.")
    if not isinstance(strategy_modes, dict) or not strategy_modes:
        raise RuntimeError("Snapshot strategy_modes is empty.")
    if not default_mode or default_mode not in strategy_modes:
        raise RuntimeError("Snapshot default_mode is missing or invalid.")


def run_generate_daily_candidates() -> dict[str, str]:
    config = load_config()
    snapshot = generate_daily_candidates()
    _validate_snapshot(snapshot)

    trade_date = snapshot["trade_date"]
    processed_dir = config.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    latest_output_path = processed_dir / "daily_candidates_latest.json"
    dated_output_path = processed_dir / f"daily_candidates_{trade_date}.json"
    write_dated_snapshot = os.getenv("A_SHARE_WRITE_DATED_SNAPSHOT") == "1"

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    latest_output_path.write_text(payload, encoding="utf-8")
    if write_dated_snapshot:
        dated_output_path.write_text(payload, encoding="utf-8")

    result = {
        "trade_date": trade_date,
        "json_output": str(latest_output_path),
        "candidate_count": str(len(snapshot.get("candidate_pool", []))),
        "default_mode": str(snapshot.get("default_mode", "")),
    }
    if write_dated_snapshot:
        result["dated_json_output"] = str(dated_output_path)
    return result


if __name__ == "__main__":
    result = run_generate_daily_candidates()
    print(json.dumps(result, ensure_ascii=False, indent=2))
