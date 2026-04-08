import json
from typing import Any, Optional

from app.core.config import get_settings


def load_latest_selection_snapshot() -> Optional[dict[str, Any]]:
    settings = get_settings()
    snapshot_path = settings.data_dir / "processed" / "daily_candidates_latest.json"
    if not snapshot_path.exists():
        return None
    return json.loads(snapshot_path.read_text(encoding="utf-8"))


def list_snapshot_modes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if snapshot.get("mode_summaries"):
        return snapshot["mode_summaries"]

    return [
        {
            "mode_id": snapshot.get("default_mode", "balanced"),
            "display_name": "综合研判",
            "description": "默认综合模式。",
            "holding_window": "3-5D",
        }
    ]


def resolve_snapshot_mode(
    snapshot: dict[str, Any], requested_mode: Optional[str] = None
) -> tuple[str, dict[str, Any]]:
    strategy_modes = snapshot.get("strategy_modes")
    if not strategy_modes:
        mode_id = requested_mode or snapshot.get("default_mode", "balanced")
        return (
            mode_id,
            {
                "mode_id": mode_id,
                "display_name": "综合研判",
                "description": "默认综合模式。",
                "holding_window": "3-5D",
                "items": snapshot.get("candidate_pool", []),
                "stock_details": snapshot.get("stock_details", {}),
                "selection_meta": snapshot.get("selection_meta", {}),
            },
        )

    default_mode = snapshot.get("default_mode") or next(iter(strategy_modes))
    selected_mode = requested_mode or default_mode
    if selected_mode not in strategy_modes:
        raise KeyError(selected_mode)
    return selected_mode, strategy_modes[selected_mode]
