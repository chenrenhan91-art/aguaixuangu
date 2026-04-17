from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import akshare as ak


@dataclass(frozen=True)
class TradeDayStatus:
    trade_date: str
    is_trade_day: bool
    source: str
    reason: str


def _load_trade_dates_from_akshare() -> set[str]:
    df = ak.tool_trade_date_hist_sina()
    if "trade_date" not in df.columns:
        raise RuntimeError("AKShare 交易日历缺少 trade_date 字段。")
    return {str(value) for value in df["trade_date"].astype(str).tolist()}


def detect_trade_day(target_date: date | None = None, force_refresh: bool = False) -> TradeDayStatus:
    current = target_date or date.today()
    trade_date = current.isoformat()

    if force_refresh:
        return TradeDayStatus(
            trade_date=trade_date,
            is_trade_day=True,
            source="manual_override",
            reason="检测到手动强制刷新，跳过交易日限制。",
        )

    try:
        trade_dates = _load_trade_dates_from_akshare()
        is_trade_day = trade_date in trade_dates
        return TradeDayStatus(
            trade_date=trade_date,
            is_trade_day=is_trade_day,
            source="akshare_trade_calendar",
            reason="命中 A 股交易日。" if is_trade_day else "当前日期不在 A 股交易日历内，自动跳过刷新。",
        )
    except Exception as exc:  # pragma: no cover - fallback path depends on external service
        weekday_trade_day = current.weekday() < 5
        return TradeDayStatus(
            trade_date=trade_date,
            is_trade_day=weekday_trade_day,
            source="weekday_fallback",
            reason=f"交易日历服务不可用，已回退到工作日判断：{type(exc).__name__}: {exc}",
        )


def _write_github_output(output_path: str | None, payload: TradeDayStatus) -> None:
    if not output_path:
        return
    path = Path(output_path)
    lines = [
        f"trade_date={payload.trade_date}",
        f"is_trade_day={'true' if payload.is_trade_day else 'false'}",
        f"calendar_source={payload.source}",
        f"calendar_reason={payload.reason}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether today is an A-share trading day.")
    parser.add_argument("--date", dest="trade_date", help="Target date in YYYY-MM-DD format.")
    parser.add_argument("--github-output", dest="github_output", help="GitHub Actions output file path.")
    parser.add_argument("--force", action="store_true", help="Force refresh regardless of market calendar.")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.trade_date, "%Y-%m-%d").date()
        if args.trade_date
        else None
    )
    force_refresh = args.force or os.getenv("A_SHARE_FORCE_REFRESH") == "1"
    payload = detect_trade_day(target_date=target_date, force_refresh=force_refresh)

    _write_github_output(args.github_output, payload)
    print(json.dumps(asdict(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
