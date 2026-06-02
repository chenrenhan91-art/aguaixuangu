import json
import os
import re
from pathlib import Path
from typing import Optional

from data_pipeline.config import load_config


SESSION_SNAPSHOT_PATTERN = re.compile(r"^daily_candidates_(\d{4}-\d{2}-\d{2})_(midday|close)\.json$")
LEGACY_SNAPSHOT_PATTERN = re.compile(r"^daily_candidates_(\d{4}-\d{2}-\d{2})\.json$")
SKIP_SNAPSHOT_NAMES = {"daily_candidates_latest.json", "daily_candidates_history.json"}


def _read_snapshot(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _build_session_entry(path: Path, payload: dict) -> dict:
    return {
        "path": path.name,
        "generated_at": payload.get("generated_at"),
        "default_mode": payload.get("default_mode"),
        "snapshot_session": payload.get("snapshot_session"),
        "candidate_count": len(payload.get("candidate_pool") or []),
    }


def rebuild_snapshot_history(retention: Optional[int] = None) -> dict[str, int]:
    config = load_config()
    processed_dir = config.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)
    retention = retention or int(os.environ.get("HISTORY_RETENTION", "10"))

    by_date: dict[str, dict[str, dict]] = {}

    for path in processed_dir.glob("daily_candidates_*.json"):
        match = SESSION_SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue
        payload = _read_snapshot(path)
        if payload is None:
            continue
        trade_date, session_id = match.group(1), match.group(2)
        by_date.setdefault(trade_date, {})[session_id] = _build_session_entry(path, payload)

    for path in processed_dir.glob("daily_candidates_*.json"):
        match = LEGACY_SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue
        trade_date = match.group(1)
        if trade_date in by_date:
            continue
        payload = _read_snapshot(path)
        if payload is None:
            continue
        session_id = (payload.get("snapshot_session") or {}).get("session_id") or "close"
        by_date.setdefault(trade_date, {})[session_id] = _build_session_entry(path, payload)

    sorted_dates = sorted(by_date.keys(), reverse=True)
    keep_dates = set(sorted_dates[:retention])
    pruned_count = 0

    for path in processed_dir.glob("daily_candidates_*.json"):
        if path.name in SKIP_SNAPSHOT_NAMES:
            continue
        match = SESSION_SNAPSHOT_PATTERN.match(path.name) or LEGACY_SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue
        if match.group(1) in keep_dates:
            continue
        path.unlink()
        pruned_count += 1
        print(f"Pruned old snapshot: {path.name}")

    entries = [
        {"trade_date": trade_date, "sessions": by_date[trade_date]}
        for trade_date in sorted_dates
        if trade_date in keep_dates
    ]

    index_path = processed_dir / "daily_candidates_history.json"
    index_path.write_text(
        json.dumps({"retention": retention, "entries": entries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {"entries": len(entries), "pruned": pruned_count, "retention": retention}


if __name__ == "__main__":
    print(json.dumps(rebuild_snapshot_history(), ensure_ascii=False, indent=2))