import io

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.trade_diagnostics import _standardize_rows


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_market_regime_contains_ai_sentiment() -> None:
    response = client.get("/api/market/regime")
    assert response.status_code == 200
    payload = response.json()
    assert "ai_sentiment" in payload
    assert payload["ai_sentiment"]["sentiment_label"]
    assert payload["ai_sentiment"]["tone_key"] in {"ice", "fade", "repair", "rotation", "trend"}
    assert isinstance(payload["ai_sentiment"]["playbook"], list)
    assert "temperature_value" in payload["ai_sentiment"]


def test_dashboard_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_daily_signals_endpoint() -> None:
    response = client.get("/api/signals/daily")
    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_version"] in {"v2-mvp-baseline", "v1-akshare-live", "v2-akshare-multi-mode"}
    assert payload["selected_mode"]
    assert len(payload["available_modes"]) >= 1
    assert len(payload["items"]) >= 1


def test_daily_signals_mode_switch_endpoint() -> None:
    response = client.get("/api/signals/daily", params={"mode": "event_driven"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_mode"] in {"balanced", "event_driven"}


def test_stock_detail_endpoint() -> None:
    response = client.get("/api/stocks/000977.SZ")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "000977.SZ"
    assert len(payload["feature_scores"]) >= 1
    assert "risk_plan" in payload
    assert "ai_risk_analysis" in payload


def test_regenerate_ai_risk_analysis_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.stocks.regenerate_ai_risk_analysis",
        lambda symbol, mode: {
            "status": "ai_live",
            "model": "gemini-3-pro-preview",
            "confidence": 0.82,
            "summary": f"{symbol} 的风控分析已刷新",
            "highlights": ["测试环境已替换为假数据。"],
            "next_step": "观察止盈止损位执行。",
            "source": "gemini",
            "generated_at": "2026-04-07T10:00:00+00:00",
        },
    )

    response = client.post("/api/stocks/001309/ai-risk-analysis", params={"mode": "balanced"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ai_live"
    assert payload["model"] == "gemini-3-pro-preview"


def test_trade_diagnostics_profiles_endpoint() -> None:
    response = client.get("/api/trade-diagnostics/profiles")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["profiles"]) >= 1
    assert any(field["field_name"] == "symbol" for field in payload["standard_fields"])


def test_trade_diagnostics_import_and_summary(monkeypatch, tmp_path) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    sample_csv = """成交日期,证券代码,证券名称,买卖方向,成交数量,成交价格,成交金额,佣金,印花税,过户费
2026-04-01,000001,平安银行,买入,100,10.00,1000,1,0,0
2026-04-03,000001,平安银行,卖出,100,10.90,1090,1,1.09,0
2026-04-04,000002,万科A,买入,100,11.20,1120,1,0,0
2026-04-07,000002,万科A,卖出,100,10.50,1050,1,1.05,0
"""

    response = client.post(
        "/api/trade-diagnostics/import",
        files={"file": ("sample.csv", io.BytesIO(sample_csv.encode("utf-8-sig")), "text/csv")},
        data={"profile_id": "generic_csv"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["batch"]["imported_count"] == 4
    assert payload["batch"]["symbol_count"] == 2

    summary_response = client.get("/api/trade-diagnostics/summary")
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["status"] == "live"
    assert summary_payload["latest_batch"]["imported_count"] == 4
    assert len(summary_payload["summary_metrics"]) >= 1
    assert len(summary_payload["recommendations"]) >= 1
    assert "ai_analysis" in summary_payload


def test_trade_diagnostics_standardize_wps_xls_rows() -> None:
    rows = [
        {
            "交易日期": 20240227.0,
            "证券代码": "799999",
            "证券名称": "登记指定",
            "买卖方向": "买入",
            "证券类别": "指定交易",
            "业务标志": "指定交易",
            "成交数量": "1.00",
            "成交价格": "1.00000000",
            "成交金额": "0.00",
            "清算金额": "0.00",
            "成交时间": 181426.0,
            "净佣金": "0.00",
            "风险金": "0.00",
        },
        {
            "交易日期": 20240228.0,
            "证券代码": "002713",
            "证券名称": "东易日盛",
            "买卖方向": "买入",
            "证券类别": "股票",
            "业务标志": "证券买入",
            "成交数量": "3200.00",
            "成交价格": "6.56000000",
            "成交金额": "20992.00",
            "清算金额": "-20997.21",
            "成交时间": 141907.0,
            "净佣金": "3.60",
            "风险金": "0.00",
        },
        {
            "交易日期": 20240229.0,
            "证券代码": "002713",
            "证券名称": "东易日盛",
            "买卖方向": "卖出",
            "证券类别": "股票",
            "业务标志": "证券卖出",
            "成交数量": "-3200.00",
            "成交价格": "6.58000000",
            "成交金额": "21056.00",
            "清算金额": "21040.26",
            "成交时间": 130148.0,
            "净佣金": "3.60",
            "风险金": "0.00",
        },
    ]

    trades, ignored_rows = _standardize_rows(rows, broker="其他券商", source_type="excel")

    assert len(trades) == 2
    assert ignored_rows == ["row-1"]
    assert trades[0].trade_date.isoformat() == "2024-02-28"
    assert trades[0].trade_time == "14:19:07"
    assert trades[1].trade_time == "13:01:48"
    assert trades[1].side == "sell"
    assert trades[1].quantity == 3200
    assert trades[1].net_amount == 21040.26


def test_trade_diagnostics_ai_analysis_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.trade_diagnostics.regenerate_trade_diagnostics_ai_analysis",
        lambda batch_id=None: {
            "status": "ai_live",
            "model": "gemini-3-pro-preview",
            "confidence": 0.81,
            "summary": "当前更适合保留顺势波段，压缩临盘追价。",
            "trader_profile": "当前更接近顺势波段型交易者。",
            "strengths": ["主线共振时更容易拿住盈利单。"],
            "weaknesses": ["追高后回落仍是主要亏损来源。"],
            "behavior_tags": ["顺势波段", "追高回撤"],
            "adjustments": ["只做主线确认后的第一次回踩。"],
            "next_cycle_plan": ["先筛主线", "再等确认", "最后统一复盘"],
            "source": "gemini",
            "generated_at": "2026-04-08T09:30:00+00:00",
        },
    )

    response = client.post("/api/trade-diagnostics/ai-analysis", params={"batch_id": "demo-batch"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ai_live"
    assert payload["model"] == "gemini-3-pro-preview"
    assert payload["trader_profile"]
