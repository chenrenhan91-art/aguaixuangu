from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from data_pipeline.config import load_config
from data_pipeline.selection_engine import STRATEGY_MODES, generate_daily_candidates

_BEIJING_TZ = ZoneInfo("Asia/Shanghai")
_MIDDAY_END_MINUTE = 14 * 60 + 30
_CLOSE_START_MINUTE = 15 * 60
_EXPECTED_MODE_IDS = tuple(mode.mode_id for mode in STRATEGY_MODES)
_DEPRECATED_MODE_IDS = {"sector_rotation", "short_term_relay"}


def _validate_snapshot(snapshot: dict) -> None:
    candidate_pool = snapshot.get("candidate_pool")
    strategy_modes = snapshot.get("strategy_modes")
    default_mode = snapshot.get("default_mode")
    mode_summaries = snapshot.get("mode_summaries")
    snapshot_session = snapshot.get("snapshot_session") or {}

    if not isinstance(candidate_pool, list) or not candidate_pool:
        raise RuntimeError("Snapshot candidate_pool is empty.")
    if not isinstance(strategy_modes, dict) or not strategy_modes:
        raise RuntimeError("Snapshot strategy_modes is empty.")
    if not default_mode or default_mode not in strategy_modes:
        raise RuntimeError("Snapshot default_mode is missing or invalid.")
    if snapshot_session.get("session_id") not in ("midday", "close"):
        raise RuntimeError("Snapshot session_id is missing or invalid.")

    expected_modes = set(_EXPECTED_MODE_IDS)
    actual_modes = set(strategy_modes)
    missing_modes = sorted(expected_modes - actual_modes)
    deprecated_modes = sorted(_DEPRECATED_MODE_IDS & actual_modes)
    if missing_modes:
        raise RuntimeError(f"Snapshot strategy_modes missing current modes: {missing_modes}.")
    if deprecated_modes:
        raise RuntimeError(f"Snapshot contains deprecated strategy modes: {deprecated_modes}.")

    summary_ids = {
        str(item.get("mode_id"))
        for item in mode_summaries
        if isinstance(item, dict) and item.get("mode_id")
    } if isinstance(mode_summaries, list) else set()
    missing_summaries = sorted(expected_modes - summary_ids)
    if missing_summaries:
        raise RuntimeError(f"Snapshot mode_summaries missing current modes: {missing_summaries}.")

    for mode_id in _EXPECTED_MODE_IDS:
        mode_payload = strategy_modes.get(mode_id) or {}
        items = mode_payload.get("items")
        details = mode_payload.get("stock_details")
        if not isinstance(items, list) or not items:
            raise RuntimeError(f"Snapshot mode has no candidates: {mode_id}.")
        if len(items) > 5:
            raise RuntimeError(f"Snapshot mode has too many candidates (>5): {mode_id}.")
        if not isinstance(details, dict) or not details:
            raise RuntimeError(f"Snapshot mode stock_details is empty: {mode_id}.")
        for item in items:
            symbol = str(item.get("symbol") or "").zfill(6)
            if len(symbol) != 6 or not symbol.isdigit():
                raise RuntimeError(f"Snapshot mode has invalid symbol: {mode_id}.")
            detail = details.get(symbol)
            if not isinstance(detail, dict):
                raise RuntimeError(f"Snapshot detail missing for {mode_id}/{symbol}.")
            if not detail.get("risk_plan"):
                raise RuntimeError(f"Snapshot risk_plan missing for {mode_id}/{symbol}.")


def _is_reusable_current_snapshot(snapshot: dict | None) -> bool:
    if not snapshot:
        return False
    try:
        _validate_snapshot(snapshot)
    except Exception as exc:
        print(f"[fast-path] existing snapshot is stale or invalid, regenerating: {exc}")
        return False
    return True


def _read_existing_snapshot(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_latest_snapshot(processed_dir: Path, snapshot: dict) -> Path:
    latest_output_path = processed_dir / "daily_candidates_latest.json"
    latest_output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest_output_path


def _reuse_existing_session_snapshot(processed_dir: Path, session_path: Path, snapshot: dict) -> dict[str, str]:
    latest_output_path = _write_latest_snapshot(processed_dir, snapshot)
    return {
        "trade_date": snapshot.get("trade_date", ""),
        "json_output": str(latest_output_path),
        "candidate_count": str(len(snapshot.get("candidate_pool", []))),
        "default_mode": str(snapshot.get("default_mode", "")),
        "dated_json_output": str(session_path),
    }


def _force_snapshot_session(snapshot: dict, session_id: str) -> dict:
    if session_id not in ("midday", "close"):
        return snapshot
    snap_session = dict(snapshot.get("snapshot_session") or {})
    snap_session["session_id"] = session_id
    snap_session["label"] = "午盘信息" if session_id == "midday" else "收盘信息"
    return {**snapshot, "snapshot_session": snap_session}


def run_generate_daily_candidates() -> dict[str, str]:
    config = load_config()
    processed_dir = config.processed_data_dir
    processed_dir.mkdir(parents=True, exist_ok=True)

    write_dated_snapshot = os.getenv("A_SHARE_WRITE_DATED_SNAPSHOT") == "1"
    session_target = os.getenv("A_SHARE_SNAPSHOT_SESSION_TARGET", "").strip().lower()
    if session_target not in ("midday", "close"):
        session_target = ""

    # ---------------------------------------------------------------------------
    # 快速退出路径：午盘目标是在 13:30 下午开盘前完成推送；若当天午盘快照已经
    # 由前序 cron job 生成并推送，则后续午盘重试直接沿用，跳过完整的数据抓取管道。
    # <14:30 的扩展窗口只用于 GitHub Actions 严重延迟时的恢复，不作为常规目标。
    # 这解决了 9 个午盘 cron 排队时各自重跑完整管道（每次 15-25 min）的问题。
    # ---------------------------------------------------------------------------
    now_bj = datetime.now(tz=_BEIJING_TZ)
    _minute_of_day = now_bj.hour * 60 + now_bj.minute
    if write_dated_snapshot:
        _today_bj = now_bj.strftime("%Y-%m-%d")
        _midday_fast_path = processed_dir / f"daily_candidates_{_today_bj}_midday.json"
        _close_fast_path = processed_dir / f"daily_candidates_{_today_bj}_close.json"
        _existing_midday = _read_existing_snapshot(_midday_fast_path)
        _existing_close = _read_existing_snapshot(_close_fast_path)

        if (
            _is_reusable_current_snapshot(_existing_close)
            and session_target == "midday"
            and _minute_of_day >= _CLOSE_START_MINUTE
        ):
            print(f"[fast-path] {_today_bj} 收盘快照已存在，跳过晚到的午盘备援任务。")
            return _reuse_existing_session_snapshot(processed_dir, _close_fast_path, _existing_close)

        if (
            _is_reusable_current_snapshot(_existing_close)
            and (session_target == "close" or (not session_target and _minute_of_day >= _CLOSE_START_MINUTE))
        ):
            print(f"[fast-path] {_today_bj} 收盘快照已存在，跳过完整管道。")
            return _reuse_existing_session_snapshot(processed_dir, _close_fast_path, _existing_close)

        if _is_reusable_current_snapshot(_existing_midday):
            should_reuse_midday = session_target == "midday" or (not session_target and _minute_of_day < _MIDDAY_END_MINUTE)
            if should_reuse_midday:
                print(f"[fast-path] {_today_bj} 午盘快照已存在，跳过完整管道。")
                return _reuse_existing_session_snapshot(processed_dir, _midday_fast_path, _existing_midday)

    snapshot = generate_daily_candidates()
    _validate_snapshot(snapshot)
    if session_target:
        snapshot = _force_snapshot_session(snapshot, session_target)

    trade_date = snapshot["trade_date"]
    latest_output_path = processed_dir / "daily_candidates_latest.json"
    dated_output_path = processed_dir / f"daily_candidates_{trade_date}.json"

    session_id = snapshot.get("snapshot_session", {}).get("session_id", "")
    if write_dated_snapshot and session_id == "midday":
        midday_output_path = processed_dir / f"daily_candidates_{trade_date}_midday.json"
        existing_midday = _read_existing_snapshot(midday_output_path)
        if existing_midday:
            # Keep the first successful midday snapshot unchanged.
            snapshot = existing_midday
    elif write_dated_snapshot and session_id == "close":
        close_output_path = processed_dir / f"daily_candidates_{trade_date}_close.json"
        existing_close = _read_existing_snapshot(close_output_path)
        if existing_close:
            # Keep the first successful close snapshot unchanged; late GitHub
            # watchdog runs should not make the frontend show a 21:30 close.
            snapshot = existing_close

    # State-based fallback: if the time-based heuristic labelled this run
    # "close" but no midday file has been written yet for today and it is
    # still before 15:00 Beijing, treat this as the midday snapshot.  This
    # covers the rare case where GitHub Actions delays ALL cron triggers past
    # the 14:30 midday boundary so none of them get labelled "midday".
    if write_dated_snapshot and session_id == "close":
        midday_output_path = processed_dir / f"daily_candidates_{trade_date}_midday.json"
        if not midday_output_path.exists():
            now_bj = datetime.now(tz=_BEIJING_TZ)
            if now_bj.hour < 15:
                snap_session = dict(snapshot.get("snapshot_session") or {})
                snap_session["session_id"] = "midday"
                snap_session["label"] = "午盘信息"
                snapshot = {**snapshot, "snapshot_session": snap_session}
                session_id = "midday"

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    latest_output_path.write_text(payload, encoding="utf-8")
    if write_dated_snapshot:
        dated_output_path.write_text(payload, encoding="utf-8")
        # Also write a session-specific file so midday and close snapshots
        # coexist on disk and can be loaded independently by the frontend.
        session_id = snapshot.get("snapshot_session", {}).get("session_id", "")
        if session_id in ("midday", "close"):
            session_output_path = processed_dir / f"daily_candidates_{trade_date}_{session_id}.json"
            session_output_path.write_text(payload, encoding="utf-8")

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
