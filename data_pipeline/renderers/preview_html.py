import json
import sys
from copy import deepcopy
from pathlib import Path


def load_cached_ai_analysis(output_path: Path) -> dict:
    cache_path = output_path.parent / "data" / "processed" / "ai_risk_analysis_cache.json"
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def merge_cached_ai_analysis(snapshot: dict, output_path: Path) -> dict:
    hydrated_snapshot = deepcopy(snapshot)
    cache = load_cached_ai_analysis(output_path)
    if not cache:
        return hydrated_snapshot

    for mode_id, payload in hydrated_snapshot.get("strategy_modes", {}).items():
        stock_details = payload.get("stock_details", {})
        for symbol, detail in stock_details.items():
            cached = cache.get(f"{mode_id}:{symbol}")
            if cached:
                detail["ai_risk_analysis"] = cached

    return hydrated_snapshot


def load_trade_preview_payload() -> tuple[dict, dict]:
    backend_root = Path(__file__).resolve().parents[2] / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    try:
        from app.schemas.trade_diagnostics import ImportProfilesResponse, TradeDiagnosticsResponse
        from app.services.trade_diagnostics import get_import_profiles, get_trade_diagnostics

        profiles = get_import_profiles()
        diagnostics = get_trade_diagnostics()
        return (
            json.loads(ImportProfilesResponse.model_validate(profiles).model_dump_json()),
            json.loads(TradeDiagnosticsResponse.model_validate(diagnostics).model_dump_json()),
        )
    except Exception:
        return (
            {
                "profiles": [
                    {
                        "profile_id": "generic_csv",
                        "display_name": "通用 CSV / Excel",
                        "broker": "其他券商",
                        "supported_extensions": [".csv", ".xlsx"],
                        "recommended_format": "CSV 优先",
                        "description": "离线版建议优先使用 CSV，本页支持本地即时解析。",
                        "export_steps": [
                            "从券商客户端导出历史成交或交割单明细。",
                            "保留日期、代码、方向、数量、价格等核心字段。",
                            "若要离线页面直接解析，建议优先导出为 CSV。",
                        ],
                    }
                ],
                "standard_fields": [
                    {
                        "field_name": "trade_date",
                        "display_name": "成交日期",
                        "required": True,
                        "description": "支持 YYYY-MM-DD、YYYY/MM/DD、YYYYMMDD。",
                    },
                    {
                        "field_name": "symbol",
                        "display_name": "证券代码",
                        "required": True,
                        "description": "系统会自动补齐为 6 位代码。",
                    },
                    {
                        "field_name": "side",
                        "display_name": "买卖方向",
                        "required": True,
                        "description": "支持 买入 / 卖出 / buy / sell。",
                    },
                    {
                        "field_name": "quantity",
                        "display_name": "成交数量",
                        "required": True,
                        "description": "整数股数。",
                    },
                    {
                        "field_name": "price",
                        "display_name": "成交价格",
                        "required": True,
                        "description": "单笔成交均价或成交价。",
                    },
                ],
            },
            {
                "status": "demo",
                "account_label": "离线演示账户",
                "coverage_text": "当前显示的是示例诊断，导入 CSV 后可在本页即时刷新。",
                "latest_batch": None,
                "summary_metrics": [
                    {"label": "闭环交易数", "value": "36", "detail": "示例数据中的已完成买卖配对。"},
                    {"label": "胜率", "value": "52.8%", "detail": "盈利单占比略高，但稳定性一般。"},
                    {"label": "盈亏比", "value": "1.34", "detail": "总盈利 / 总亏损。"},
                    {"label": "平均持仓", "value": "4.6 天", "detail": "更接近 3-8 天的短波段打法。"},
                ],
                "style_profile": {
                    "style_id": "swing_short",
                    "display_name": "短波段交易型",
                    "confidence": 0.76,
                    "summary": "盈利主要来自趋势延续阶段的 3 到 8 天持有，频繁换股会明显拉低表现。",
                    "traits": ["偏好热点行业龙头", "更适合确认后跟随", "不适合高频冲动交易"],
                },
                "win_loss_comparison": [
                    {"label": "盈利单平均持有", "value": "6.1 天", "detail": "赚钱时更愿意耐心持有。"},
                    {"label": "亏损单平均持有", "value": "2.4 天", "detail": "止损尚算及时，但容易追高后回撤。"},
                    {"label": "盈利单平均收益", "value": "+8.2%", "detail": "大多来自顺势延续与二次突破。"},
                    {"label": "亏损单平均回撤", "value": "-5.9%", "detail": "集中在情绪高位接力与弱势环境出手。"},
                ],
                "error_patterns": [
                    {
                        "title": "热点追高后回落",
                        "detail": "亏损单多数发生在放量冲高次日才介入，买点偏后。",
                        "severity": "medium",
                    }
                ],
                "effective_patterns": [
                    {
                        "title": "板块共振时顺势跟随有效",
                        "detail": "行业主线明确、成交额同步放大时，交易胜率更高。",
                        "severity": "positive",
                    }
                ],
                "recommendations": [
                    "把主要精力放在 3 到 8 天的趋势延续交易，不必追求日内频繁切换。",
                    "热点股只做第一次回踩确认，不在连续加速后再追入。",
                ],
                "recent_batches": [],
            },
        )


def load_market_preview_payload(snapshot: dict) -> dict:
    backend_root = Path(__file__).resolve().parents[2] / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    try:
        from app.schemas.market import MarketRegimeResponse
        from app.services.ai_market_sentiment import get_effective_market_sentiment

        market = snapshot.get("market_regime", {}) or {}
        payload = {
            "regime": market.get("regime", "neutral"),
            "confidence": market.get("confidence", 0.5),
            "suggested_exposure": market.get("suggested_exposure", 0.5),
            "breadth_score": market.get("breadth_score", 50.0),
            "northbound_score": market.get("northbound_score", 50.0),
            "momentum_score": market.get("momentum_score", 50.0),
            "updated_at": market.get("updated_at"),
            "ai_sentiment": get_effective_market_sentiment(snapshot),
        }
        return json.loads(MarketRegimeResponse.model_validate(payload).model_dump_json())
    except Exception:
        market = snapshot.get("market_regime", {}) or {}
        return {
            "regime": market.get("regime", "neutral"),
            "confidence": market.get("confidence", 0.5),
            "suggested_exposure": market.get("suggested_exposure", 0.5),
            "breadth_score": market.get("breadth_score", 50.0),
            "northbound_score": market.get("northbound_score", 50.0),
            "momentum_score": market.get("momentum_score", 50.0),
            "updated_at": market.get("updated_at"),
            "ai_sentiment": {
                "status": "fallback_rules",
                "sentiment_label": "轮动博弈",
                "sentiment_score": 55.0,
                "tone_key": "rotation",
                "temperature_value": 55.0,
                "temperature_label": "暖区轮动段",
                "summary": "当前按轮动博弈处理，盘前只看更靠前的主线排序。",
                "action_bias": "控仓观察",
                "tags": ["先看主线", "排序优先", "节奏放慢"],
                "watchouts": ["优先围绕主线排序靠前的方向做观察。"],
                "playbook": [
                    "围绕最强两条主线做切换，不要同时分散铺仓。",
                    "优先看排序靠前且量价确认更完整的候选股。",
                    "盘中若主线切换加快，要及时去弱留强。",
                ],
                "source": "rules",
            },
        }


TEMPLATE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>A股 AI 选股工具</title>
    <style>
__EMBEDDED_CSS__

      .preview-shell {
        width: min(1580px, calc(100vw - 24px));
        margin: 0 auto;
        padding: 12px 0 18px;
      }

      .view-tabs {
        display: flex;
        gap: 8px;
        margin-top: 10px;
        flex-wrap: wrap;
      }

      .view-tab {
        min-height: 38px;
        padding: 0 14px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(10, 19, 30, 0.94);
        color: var(--text-dim);
        cursor: pointer;
        transition:
          transform 140ms ease,
          border-color 140ms ease,
          background 140ms ease;
      }

      .view-tab:hover,
      .view-tab.active {
        transform: translateY(-1px);
        border-color: var(--line-strong);
        background: rgba(18, 31, 46, 0.98);
        color: #f6fbff;
      }

      .view-page {
        margin-top: 10px;
      }

      .view-page.is-hidden {
        display: none;
      }

      .selector-overview-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.38fr) minmax(300px, 0.92fr) minmax(320px, 0.96fr);
        gap: 10px;
        align-items: stretch;
      }

      .selector-overview-card {
        border: 1px solid var(--line);
        border-radius: 14px;
        background:
          linear-gradient(90deg, rgba(255, 181, 58, 0.06), transparent 22%),
          linear-gradient(180deg, rgba(9, 18, 28, 0.98), rgba(10, 19, 29, 0.98));
        padding: 13px 14px;
        min-height: 150px;
      }

      .market-emotion-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-top: 6px;
      }

      .market-emotion-row strong {
        font-size: 1.3rem;
        letter-spacing: -0.03em;
        color: #f8fbff;
      }

      .micro-metric-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin-top: 12px;
      }

      .micro-metric {
        border-radius: 10px;
        padding: 10px 11px;
        background: rgba(12, 22, 34, 0.92);
        border: 1px solid rgba(124, 150, 176, 0.12);
      }

      .micro-metric span {
        display: block;
        color: var(--text-soft);
        font-size: 0.76rem;
      }

      .micro-metric strong {
        display: block;
        margin-top: 6px;
        color: #f7fbff;
        font-size: 1.02rem;
      }

      .preview-grid {
        margin-top: 10px;
        display: grid;
        grid-template-columns: minmax(310px, 0.92fr) minmax(0, 2.46fr);
        gap: 10px;
        align-items: start;
      }

      .preview-rail {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      .analysis-grid {
        min-width: 0;
        display: grid;
        grid-template-columns: minmax(360px, 0.92fr) minmax(0, 1.7fr);
        gap: 10px;
        align-items: stretch;
      }

      .detail-bottom-grid {
        grid-column: 1 / -1;
      }

      .preview-rail .panel {
        min-height: 0;
      }

      .preview-mode-card,
      .upload-note-card,
      .trade-card,
      .trade-insight-card,
      .field-card,
      .style-card,
      .batch-card,
      .guide-card {
        border: 1px solid rgba(124, 150, 176, 0.14);
        border-radius: 10px;
        padding: 10px 11px;
        background: rgba(12, 22, 34, 0.96);
      }

      .preview-mode-card p,
      .upload-note-card p,
      .trade-card p,
      .trade-insight-card p,
      .field-card p,
      .style-card p,
      .batch-card p,
      .guide-card p {
        margin: 6px 0 0;
        color: var(--text-dim);
        font-size: 0.84rem;
        line-height: 1.52;
      }

      .preview-mode-card {
        margin-top: 10px;
      }

      .mode-summary-title,
      .style-title-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
      }

      .mode-summary-title span,
      .style-title-row span,
      .trade-card span {
        color: var(--accent-strong);
        font-size: 1.02rem;
        letter-spacing: -0.03em;
      }

      .diagnostics-layout {
        display: grid;
        grid-template-columns: minmax(320px, 0.88fr) minmax(760px, 1.68fr);
        gap: 10px;
        align-items: start;
      }

      .diagnostics-main,
      .diagnostics-sidebar {
        min-width: 0;
      }

      .diagnostics-main .panel,
      .diagnostics-sidebar .panel {
        min-height: 0;
      }

      .import-form {
        display: grid;
        gap: 10px;
      }

      .field-group {
        display: grid;
        gap: 6px;
      }

      .field-group span {
        color: var(--text-dim);
        font-size: 0.82rem;
      }

      .field-group select,
      .field-group input[type="file"] {
        width: 100%;
        padding: 10px 11px;
        border-radius: 10px;
        border: 1px solid var(--line);
        background: rgba(10, 18, 28, 0.98);
        color: #f4f8fc;
      }

      .primary-button {
        min-height: 42px;
        border: 1px solid rgba(255, 181, 58, 0.32);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(255, 181, 58, 0.18), rgba(78, 208, 255, 0.12));
        color: #f8fbff;
        cursor: pointer;
      }

      .primary-button:disabled {
        cursor: not-allowed;
        opacity: 0.56;
      }

      .upload-note-card {
        margin-top: 10px;
        border-left: 3px solid rgba(78, 208, 255, 0.72);
      }

      .trade-summary-grid,
      .trade-compare-grid,
      .field-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        margin-top: 10px;
      }

      .trade-summary-grid.four-col {
        grid-template-columns: repeat(4, minmax(0, 1fr));
      }

      .trade-card {
        min-height: 112px;
      }

      .tag-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }

      .tag-row span {
        display: inline-flex;
        align-items: center;
        padding: 3px 7px;
        border-radius: 999px;
        border: 1px solid rgba(124, 150, 176, 0.18);
        color: var(--text-dim);
        background: rgba(255, 255, 255, 0.03);
        font-size: 0.74rem;
      }

      .insight-two-col {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 10px;
      }

      .trade-insight-card.negative {
        border-left: 3px solid rgba(255, 111, 125, 0.82);
      }

      .trade-insight-card.positive {
        border-left: 3px solid rgba(69, 212, 131, 0.78);
      }

      .trade-insight-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .guide-list,
      .helper-list,
      .recommendation-list {
        margin: 8px 0 0;
        padding-left: 18px;
      }

      .guide-list li + li,
      .helper-list li + li,
      .recommendation-list li + li {
        margin-top: 6px;
      }

      .guide-list li,
      .helper-list li,
      .recommendation-list li {
        color: var(--text-dim);
        font-size: 0.84rem;
      }

      .accordion {
        margin-top: 10px;
        border: 1px solid rgba(124, 150, 176, 0.12);
        border-radius: 10px;
        background: rgba(11, 19, 30, 0.96);
      }

      .accordion summary {
        cursor: pointer;
        list-style: none;
        padding: 10px 11px;
        color: #f6fbff;
        font-size: 0.88rem;
      }

      .accordion summary::-webkit-details-marker {
        display: none;
      }

      .accordion-body {
        padding: 0 11px 11px;
      }

      .batch-list,
      .guide-list-wrap {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .view-hero {
        margin-top: 6px;
        color: var(--text-dim);
        max-width: 920px;
      }

      @media (max-width: 1380px) {
        .selector-overview-grid {
          grid-template-columns: minmax(0, 1.26fr) minmax(260px, 0.82fr) minmax(280px, 0.9fr);
        }

        .preview-grid {
          grid-template-columns: minmax(280px, 0.92fr) minmax(0, 2.28fr);
        }

        .analysis-grid {
          grid-template-columns: minmax(330px, 0.9fr) minmax(0, 1.56fr);
        }

        .diagnostics-layout {
          grid-template-columns: minmax(300px, 0.9fr) minmax(640px, 1.4fr);
        }
      }

      @media (max-width: 1180px) {
        .selector-overview-grid,
        .preview-grid,
        .diagnostics-layout {
          grid-template-columns: 1fr;
        }

        .analysis-grid {
          grid-template-columns: 1fr;
        }

        .micro-metric-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
      }

      @media (max-width: 760px) {
        .preview-shell {
          width: min(100vw - 14px, 100%);
          padding-top: 8px;
        }

        .trade-summary-grid,
        .trade-compare-grid,
        .field-grid,
        .trade-summary-grid.four-col,
        .insight-two-col,
        .micro-metric-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
  </head>
  <body>
    <div class="preview-shell">
      <header class="topbar">
        <div class="brand-lockup">
          <p class="eyebrow">Market Terminal</p>
          <div class="brand-title-row">
            <h1>A股 AI 选股工具</h1>
            <span class="terminal-badge">OFFLINE HTML</span>
          </div>
        </div>
        <div class="topbar-meta">
          <span id="updated-at" class="meta-pill">刷新：--</span>
          <span id="trade-date" class="meta-pill">交易日：--</span>
        </div>
      </header>

      <section class="market-strip">
        <article id="market-sentiment-tile" class="market-tile market-sentiment-tile">
          <span class="tile-label">市场情绪</span>
          <strong id="sentiment-value" class="tile-value">--</strong>
          <small id="sentiment-summary">--</small>
        </article>
        <article class="market-tile">
          <span class="tile-label">建议仓位比例</span>
          <strong id="exposure-value" class="tile-value">--</strong>
          <small>过滤器</small>
        </article>
        <article class="market-tile">
          <span class="tile-label">强势行业数</span>
          <strong id="sector-count-value" class="tile-value">--</strong>
          <small>当日</small>
        </article>
        <article class="market-tile">
          <span class="tile-label">候选股数量</span>
          <strong id="signal-count-value" class="tile-value">--</strong>
          <small>当日</small>
        </article>
      </section>

      <nav class="view-tabs">
        <button type="button" class="view-tab active" data-view="selector">盘前选股终端</button>
        <button type="button" class="view-tab" data-view="diagnostics">历史交易诊断</button>
      </nav>

      <section id="selector-view" class="view-page">
        <div class="selector-overview-grid">
          <article id="sentiment-overview-card" class="selector-overview-card sentiment-overview-card">
            <div class="detail-subhead">
              <h3>市场情绪</h3>
              <span id="sentiment-temperature-label" class="subhead-meta">--</span>
            </div>
            <div class="market-emotion-row">
              <strong id="sentiment-headline" class="sentiment-headline">--</strong>
              <span id="sentiment-action-bias" class="emotion-bias-chip">--</span>
            </div>
            <p id="sentiment-hero-summary" class="body-copy">--</p>
            <div class="sentiment-temperature-panel">
              <div class="temperature-meta-row">
                <span>情绪温度</span>
                <strong id="sentiment-temperature-value">--</strong>
              </div>
              <div class="temperature-bar-track">
                <div id="sentiment-temperature-fill" class="temperature-bar-fill"></div>
              </div>
            </div>
            <div id="sentiment-tag-row" class="tag-row"></div>
          </article>

          <article id="sentiment-playbook-card" class="selector-overview-card">
            <div class="detail-subhead">
              <h3>策略</h3>
              <span class="subhead-meta">Playbook</span>
            </div>
            <p id="sentiment-action-note" class="body-copy">--</p>
            <ul id="sentiment-playbook" class="recommendation-list"></ul>
          </article>

          <article id="sentiment-watch-card" class="selector-overview-card">
            <div class="detail-subhead">
              <h3>留意</h3>
              <span class="subhead-meta">Watch</span>
            </div>
            <div class="micro-metric-grid">
              <div class="micro-metric">
                <span>广度</span>
                <strong id="breadth-metric">--</strong>
              </div>
              <div class="micro-metric">
                <span>动量</span>
                <strong id="momentum-metric">--</strong>
              </div>
              <div class="micro-metric">
                <span>北向</span>
                <strong id="northbound-metric">--</strong>
              </div>
            </div>
            <ul id="sentiment-watchouts" class="recommendation-list"></ul>
          </article>
        </div>

        <div class="preview-grid">
          <aside class="preview-rail">
            <section class="panel">
              <div class="panel-header">
                <h2>行业主线</h2>
              </div>
              <div id="sector-summary-bar" class="sector-summary-bar"></div>
              <div id="sector-list" class="stack-list"></div>
            </section>

            <section class="panel">
              <div class="panel-header">
                <h2>策略模式</h2>
              </div>
              <div id="mode-toolbar" class="mode-toolbar"></div>
              <div id="mode-summary" class="preview-mode-card"></div>
            </section>
          </aside>

          <div class="analysis-grid">
            <section class="panel candidates-panel">
              <div class="panel-header">
                <h2>今日候选池</h2>
                <p id="signal-subtitle">--</p>
              </div>
              <div id="signal-list" class="signal-list"></div>
            </section>

            <section class="panel detail-overview-panel">
              <div class="panel-header detail-header detail-header-row">
                <div class="detail-header-main">
                  <h2>个股总览</h2>
                  <p id="detail-subtitle">--</p>
                </div>
                <div class="ai-action-row header-action-row">
                  <button id="refresh-ai-risk-button" type="button" class="ai-action-button">
                    AI 交易执行分析
                  </button>
                </div>
              </div>

              <div class="detail-overview-stack">
                <div id="detail-quick-grid" class="detail-quick-grid"></div>

                <div class="detail-block insight-block">
                  <div class="detail-subhead">
                    <h3>核心判断</h3>
                    <span class="subhead-meta">Research Thesis</span>
                  </div>
                  <p id="detail-thesis" class="body-copy">--</p>
                  <div id="detail-reason-tags" class="tag-row"></div>
                  <div id="detail-reason-list" class="selection-reason-list"></div>
                  <p id="detail-market-context" class="secondary-copy"></p>
                </div>

                <div class="detail-block feature-block">
                  <div class="detail-subhead">
                    <h3>核心特征</h3>
                    <span class="subhead-meta">Score Matrix</span>
                  </div>
                  <div id="feature-grid" class="feature-grid"></div>
                </div>
              </div>
            </section>

            <div class="detail-bottom-grid">
              <section class="panel event-panel">
                <div class="detail-subhead">
                  <h3>近期事件</h3>
                  <span class="subhead-meta">Event Stream</span>
                </div>
                <div id="event-tab-toolbar" class="event-tab-toolbar"></div>
                <div id="event-tone-toolbar" class="event-tone-toolbar"></div>
                <div id="event-list" class="stack-list"></div>
              </section>
            </div>
          </div>
        </div>
      </section>

      <section id="diagnostics-view" class="view-page is-hidden">
        <div class="diagnostics-layout">
          <aside class="diagnostics-sidebar">
            <section class="panel">
              <div class="panel-header">
                <h2>本地导入交割单</h2>
                <p id="trade-coverage-text">--</p>
              </div>
              <div id="trade-sidebar-summary" class="trade-sidebar-summary"></div>
              <form id="trade-import-form" class="import-form">
                <label class="field-group">
                  <span>导入模板</span>
                  <select id="trade-profile-select" name="profile_id"></select>
                </label>
                <label class="field-group">
                  <span>交易文件</span>
                  <input id="trade-file-input" name="file" type="file" accept=".csv,.txt,.xlsx" />
                </label>
                <button id="trade-import-button" type="submit" class="primary-button">导入</button>
                <p id="trade-import-status" class="secondary-copy">CSV / XLSX</p>
              </form>

              <div class="detail-block compact-block">
                <div class="detail-subhead">
                  <h3>导入指引</h3>
                  <span class="subhead-meta">Broker Guide</span>
                </div>
                <div id="trade-profile-guide" class="guide-list-wrap"></div>
              </div>

              <details class="accordion">
                <summary>查看支持字段与格式说明</summary>
                <div class="accordion-body">
                  <div id="trade-field-grid" class="field-grid"></div>
                </div>
              </details>

              <div class="detail-block compact-block">
                <div class="detail-subhead">
                  <h3>最近批次</h3>
                  <span class="subhead-meta">Recent Imports</span>
                </div>
                <div id="trade-batch-list" class="batch-list"></div>
              </div>
            </section>
          </aside>

          <section class="diagnostics-main">
            <section class="panel">
              <div class="panel-header">
                <h2>交易风格画像</h2>
              </div>
              <div id="trade-style-card" class="style-card"></div>
              <div id="trade-summary-grid" class="trade-summary-grid four-col"></div>
            </section>

            <section class="panel">
              <div class="panel-header">
                <h2>盈利单 vs 亏损单</h2>
              </div>
              <div id="trade-compare-grid" class="trade-compare-grid"></div>
            </section>

            <section class="panel">
              <div class="panel-header">
                <h2>诊断结论</h2>
              </div>
              <div class="insight-two-col">
                <div>
                  <div class="detail-subhead">
                    <h3>错误模式</h3>
                    <span class="subhead-meta">Avoid</span>
                  </div>
                  <div id="trade-error-list" class="trade-insight-list"></div>
                </div>
                <div>
                  <div class="detail-subhead">
                    <h3>有效模式</h3>
                    <span class="subhead-meta">Keep Doing</span>
                  </div>
                  <div id="trade-effective-list" class="trade-insight-list"></div>
                </div>
              </div>
            </section>

            <section class="panel">
              <div class="panel-header">
                <h2>策略优化建议</h2>
              </div>
              <ul id="trade-recommendation-list" class="recommendation-list"></ul>
            </section>
          </section>
        </div>
      </section>
    </div>

    <div id="ai-analysis-modal" class="ai-modal is-hidden" aria-hidden="true">
      <div id="ai-analysis-backdrop" class="ai-modal-backdrop"></div>
      <section class="ai-modal-panel" role="dialog" aria-modal="true" aria-labelledby="ai-analysis-title">
        <div class="ai-modal-header">
          <div>
            <p class="eyebrow">AI Output</p>
            <h2 id="ai-analysis-title">AI 交易执行分析</h2>
          </div>
          <button id="ai-analysis-close" type="button" class="ai-modal-close">关闭</button>
        </div>
        <div id="ai-analysis-modal-body" class="ai-modal-body">
          <p class="empty-state">--</p>
        </div>
      </section>
    </div>

    <script>
      const snapshot = __SNAPSHOT_JSON__;
      const marketPayload = __MARKET_PAYLOAD_JSON__;
      const importProfilesPayload = __TRADE_PROFILES_JSON__;
      const initialDiagnostics = __TRADE_DIAGNOSTICS_JSON__;

      const state = {
        currentView: "selector",
        selectedMode: snapshot.default_mode || "balanced",
        currentSymbol: null,
        currentEventTab: "official",
        currentEventTone: "all",
        tradeDiagnostics: initialDiagnostics,
        tradeProfiles: importProfilesPayload.profiles || [],
        tradeStandardFields: importProfilesPayload.standard_fields || [],
      };

      const CSV_HEADER_ALIASES = {
        trade_date: ["成交日期", "成交时间", "日期", "发生日期", "委托日期", "业务日期"],
        symbol: ["证券代码", "股票代码", "代码", "证券代号"],
        stock_name: ["证券名称", "股票名称", "名称", "证券简称"],
        side: ["买卖方向", "买卖标志", "业务名称", "方向", "操作"],
        quantity: ["成交数量", "数量", "成交股数", "发生数量", "成交份额"],
        price: ["成交价格", "成交均价", "均价", "价格"],
        amount: ["成交金额", "发生金额", "清算金额", "金额"],
        commission: ["佣金", "手续费", "交易佣金"],
        stamp_tax: ["印花税"],
        transfer_fee: ["过户费"],
        other_fee: ["其他费用", "规费", "杂费"],
        net_amount: ["净发生金额", "净收付", "清算净额", "发生净额"],
      };

      function formatDateTime(value) {
        return new Date(value).toLocaleString("zh-CN", {
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
      }

      function formatDate(value) {
        return new Date(value).toLocaleDateString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        });
      }

      function formatPercent(value) {
        return `${(value * 100).toFixed(1)}%`;
      }

      const SENTIMENT_THEME = {
        ice: { accent: "#6ea8ff", soft: "rgba(110, 168, 255, 0.18)", border: "rgba(110, 168, 255, 0.3)", chip: "rgba(110, 168, 255, 0.12)" },
        fade: { accent: "#8fc5ff", soft: "rgba(143, 197, 255, 0.18)", border: "rgba(143, 197, 255, 0.28)", chip: "rgba(143, 197, 255, 0.12)" },
        repair: { accent: "#f2c66b", soft: "rgba(242, 198, 107, 0.18)", border: "rgba(242, 198, 107, 0.28)", chip: "rgba(242, 198, 107, 0.12)" },
        rotation: { accent: "#ffb53a", soft: "rgba(255, 181, 58, 0.18)", border: "rgba(255, 181, 58, 0.28)", chip: "rgba(255, 181, 58, 0.12)" },
        trend: { accent: "#45d483", soft: "rgba(69, 212, 131, 0.18)", border: "rgba(69, 212, 131, 0.28)", chip: "rgba(69, 212, 131, 0.12)" },
      };

      function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
          element.textContent = value;
        }
      }

      function buildAiAnalysisMarkup(aiRiskAnalysis) {
        if (!aiRiskAnalysis) {
          return `
            <section class="ai-modal-window">
              <h3 class="ai-modal-title">AI 交易执行分析</h3>
              <p class="ai-modal-summary">模型接入后，这里会显示更细的执行结论、触发条件和失效条件。</p>
              <div class="tag-row">
                <span>模型预留</span>
                <span>弹窗输出</span>
              </div>
            </section>
          `;
        }

        const meta = [
          aiRiskAnalysis.generated_at ? `生成 ${formatDateTime(aiRiskAnalysis.generated_at)}` : null,
          aiRiskAnalysis.model || "待接入模型",
          `置信度 ${Math.round(Number(aiRiskAnalysis.confidence || 0.68) * 100)} / 100`,
        ].filter(Boolean);

        return `
          <section class="ai-modal-window">
            <div class="ai-window-head">
              <h3 class="ai-modal-title">AI 交易执行分析</h3>
              <div class="ai-window-meta">
                ${meta.map((item) => `<span class="ai-meta-chip">${item}</span>`).join("")}
              </div>
            </div>
            <div class="tag-row">
              ${aiRiskAnalysis.stance ? `<span>${aiRiskAnalysis.stance}</span>` : ""}
              ${aiRiskAnalysis.setup_quality ? `<span>结构 ${aiRiskAnalysis.setup_quality}</span>` : ""}
              ${aiRiskAnalysis.source ? `<span>${aiRiskAnalysis.source}</span>` : ""}
            </div>
            <p class="ai-modal-summary">${aiRiskAnalysis.summary}</p>
            <div class="ai-insight-grid">
              <article class="ai-insight-card full-span">
                <strong>关键观察</strong>
                <p class="ai-key-line">${aiRiskAnalysis.key_signal || aiRiskAnalysis.next_step || "--"}</p>
              </article>
              <article class="ai-insight-card">
                <strong>触发条件</strong>
                <ul class="ai-list">${(aiRiskAnalysis.trigger_points || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}</ul>
              </article>
              <article class="ai-insight-card">
                <strong>失效条件</strong>
                <ul class="ai-list">${(aiRiskAnalysis.invalidation_points || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}</ul>
              </article>
              <article class="ai-insight-card full-span">
                <strong>执行步骤</strong>
                <ul class="ai-list">${(aiRiskAnalysis.execution_plan || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}</ul>
              </article>
              <article class="ai-insight-card">
                <strong>补充判断</strong>
                <ul class="ai-list">${(aiRiskAnalysis.highlights || []).map((item) => `<li>${item}</li>`).join("") || "<li>--</li>"}</ul>
              </article>
              <article class="ai-insight-card">
                <strong>下一步</strong>
                <p class="ai-next-step">${aiRiskAnalysis.next_step || "--"}</p>
              </article>
            </div>
          </section>
        `;
      }

      function openAiAnalysisModal(aiRiskAnalysis) {
        const modal = document.getElementById("ai-analysis-modal");
        const body = document.getElementById("ai-analysis-modal-body");
        if (!modal || !body) {
          return;
        }
        body.innerHTML = buildAiAnalysisMarkup(aiRiskAnalysis);
        modal.classList.remove("is-hidden");
        modal.setAttribute("aria-hidden", "false");
      }

      function closeAiAnalysisModal() {
        const modal = document.getElementById("ai-analysis-modal");
        if (!modal) {
          return;
        }
        modal.classList.add("is-hidden");
        modal.setAttribute("aria-hidden", "true");
      }

      function applySentimentTheme(toneKey) {
        const theme = SENTIMENT_THEME[toneKey] || SENTIMENT_THEME.rotation;
        const root = document.documentElement;
        root.style.setProperty("--sentiment-accent", theme.accent);
        root.style.setProperty("--sentiment-accent-soft", theme.soft);
        root.style.setProperty("--sentiment-accent-border", theme.border);
        root.style.setProperty("--sentiment-chip-bg", theme.chip);
      }

      function getCurrentModePayload() {
        const strategyModes = snapshot.strategy_modes || {};
        return strategyModes[state.selectedMode] || strategyModes[snapshot.default_mode];
      }

      function renderMarketSentiment() {
        const sentiment = marketPayload.ai_sentiment || {};
        applySentimentTheme(sentiment.tone_key);
        setText("updated-at", marketPayload.updated_at ? `刷新：${formatDateTime(marketPayload.updated_at)}` : "刷新：--");
        setText("trade-date", `交易日：${snapshot.trade_date}`);
        setText("sentiment-value", sentiment.sentiment_label || "--");
        setText("sentiment-summary", sentiment.summary || "--");
        setText("sentiment-headline", sentiment.sentiment_label || "--");
        setText("sentiment-hero-summary", sentiment.summary || "--");
        setText("sentiment-temperature-label", sentiment.temperature_label || "温度待更新");
        setText("sentiment-temperature-value", typeof sentiment.temperature_value === "number" ? `${sentiment.temperature_value.toFixed(0)} / 100` : "--");
        setText("sentiment-action-bias", sentiment.action_bias || "--");
        setText(
          "sentiment-action-note",
          sentiment.action_bias
            ? `${sentiment.action_bias}；优先 ${sentiment.preferred_setup || "强势主线前排"}；回避 ${sentiment.avoid_action || "无承接追价"}`
            : "--",
        );
        const temperatureFill = document.getElementById("sentiment-temperature-fill");
        if (temperatureFill) {
          const width = Math.max(6, Math.min(Number(sentiment.temperature_value || 0), 100));
          temperatureFill.style.width = `${width}%`;
        }
        setText("breadth-metric", Number(marketPayload.breadth_score || 0).toFixed(1));
        setText("momentum-metric", Number(marketPayload.momentum_score || 0).toFixed(1));
        setText("northbound-metric", Number(marketPayload.northbound_score || 0).toFixed(1));

        const tagRow = document.getElementById("sentiment-tag-row");
        tagRow.innerHTML = (sentiment.tags || []).length
          ? sentiment.tags.map((item) => `<span>${item}</span>`).join("")
          : "<span>--</span>";

        const playbookList = document.getElementById("sentiment-playbook");
        playbookList.innerHTML = (sentiment.playbook || []).length
          ? sentiment.playbook.map((item) => `<li>${item}</li>`).join("")
          : "<li>--</li>";

        const watchoutList = document.getElementById("sentiment-watchouts");
        watchoutList.innerHTML = (sentiment.watchouts || []).length
          ? sentiment.watchouts.map((item) => `<li>${item}</li>`).join("")
          : "<li>--</li>";
      }

      function renderViewTabs() {
        document.querySelectorAll(".view-tab").forEach((button) => {
          const isActive = button.dataset.view === state.currentView;
          button.classList.toggle("active", isActive);
        });
        document.getElementById("selector-view").classList.toggle("is-hidden", state.currentView !== "selector");
        document.getElementById("diagnostics-view").classList.toggle("is-hidden", state.currentView !== "diagnostics");
        setText(
          "view-hero",
          state.currentView === "selector"
            ? ""
            : "",
        );
      }

      function setupViewTabs() {
        document.querySelectorAll(".view-tab").forEach((button) => {
          button.addEventListener("click", () => {
            if (!button.dataset.view || button.dataset.view === state.currentView) {
              return;
            }
            state.currentView = button.dataset.view;
            renderViewTabs();
          });
        });
      }

      function renderSectors(items) {
        const container = document.getElementById("sector-list");
        const summary = document.getElementById("sector-summary-bar");
        if (!items.length) {
          container.innerHTML = '<p class="empty-state">--</p>';
          if (summary) {
            summary.innerHTML = '<p class="empty-state">--</p>';
          }
          return;
        }
        if (summary) {
          const averageStrength = items.reduce((total, item) => total + Number(item.strength_score || 0), 0) / items.length;
          const hottestSector = items
            .slice()
            .sort((left, right) => Number(right.heat_score || 0) - Number(left.heat_score || 0))[0];
          const chips = [
            `监控主线 ${items.length} 条`,
            `Top1 ${items[0].sector_name}`,
            `平均强度 ${averageStrength.toFixed(1)}`,
            `热度最高 ${hottestSector.sector_name}`,
          ];
          summary.innerHTML = chips.map((item) => `<span class="sector-summary-chip">${item}</span>`).join("");
        }
        container.innerHTML = items
          .map(
            (sector, index) => `
            <article class="sector-card">
              <div class="sector-main-row">
                <span class="sector-rank-badge">#${index + 1}</span>
                <div class="sector-title-group">
                  <strong>${sector.sector_name}</strong>
                  <p>${sector.sector_code || "AKShare"} · 共识强度领先</p>
                </div>
                <div class="sector-score-group">
                  <span class="sector-score-value">${sector.strength_score.toFixed(1)}</span>
                  <small>主线分</small>
                </div>
              </div>
              <div class="sector-metrics">
                <span>强度 ${sector.strength_score.toFixed(1)}</span>
                <span>动量 ${sector.momentum_score.toFixed(1)}</span>
                <span>热度 ${sector.heat_score.toFixed(1)}</span>
              </div>
              <p class="sector-note">关注主线。</p>
            </article>
          `,
          )
          .join("");
      }

      function renderModeToolbar() {
        const container = document.getElementById("mode-toolbar");
        const modes = snapshot.mode_summaries || [];
        container.innerHTML = "";
        modes.forEach((mode) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = `mode-chip${mode.mode_id === state.selectedMode ? " active" : ""}`;
          button.innerHTML = `<strong>${mode.display_name}</strong><small>${mode.description}</small>`;
          button.addEventListener("click", () => {
            state.selectedMode = mode.mode_id;
            renderModeToolbar();
            renderModeSummary();
            renderModeSignals();
          });
          container.appendChild(button);
        });
      }

      function renderModeSummary() {
        const container = document.getElementById("mode-summary");
        const mode = (snapshot.mode_summaries || []).find((item) => item.mode_id === state.selectedMode);
        const payload = getCurrentModePayload();
        if (!mode || !payload) {
          container.innerHTML = '<p class="empty-state">--</p>';
          return;
        }
        container.innerHTML = `
          <div class="mode-summary-title">
            <strong>${mode.display_name}</strong>
            <span>${payload.items.length} 只</span>
          </div>
          <p>${mode.description}</p>
          <ul class="helper-list">
            <li>${mode.holding_window}</li>
            <li>主线优先</li>
            <li>同步联动</li>
          </ul>
        `;
      }

      function renderSignalList(items) {
        const container = document.getElementById("signal-list");
        const visibleItems = items.slice(0, 5);
        if (!visibleItems.length) {
          container.style.removeProperty("--candidate-count");
          container.innerHTML = '<p class="empty-state">--</p>';
          return;
        }
        container.style.setProperty("--candidate-count", String(Math.max(visibleItems.length, 1)));
        container.innerHTML = "";
        visibleItems.forEach((item) => {
          const tags = (item.event_tags || []).slice(0, 3);
          const button = document.createElement("button");
          button.type = "button";
          button.className = `signal-item${item.symbol === state.currentSymbol ? " active" : ""}`;
          button.innerHTML = `
            <div class="signal-main-row">
              <span class="signal-rank-badge">#${item.rank}</span>
              <div class="signal-title-group">
                <strong>${item.name}</strong>
                <small>${item.symbol}</small>
              </div>
              <div class="signal-score-group">
                <span class="signal-score-value">${item.risk_adjusted_score.toFixed(1)}</span>
                <small>模式分</small>
              </div>
            </div>
            <div class="signal-meta-row">
              <span class="signal-meta-chip primary">${item.holding_window}</span>
              <span class="signal-meta-chip">基础分 ${item.base_score.toFixed(1)}</span>
              <span class="signal-meta-chip">事件分 ${item.event_score.toFixed(1)}</span>
            </div>
            <div class="signal-tag-row">
              ${
                tags.length
                  ? tags.map((tag) => `<span class="signal-tag-pill">${tag}</span>`).join("")
                  : '<span class="signal-tag-pill">无新增事件标签</span>'
              }
            </div>
          `;
          button.addEventListener("click", () => {
            state.currentSymbol = item.symbol;
            renderSignalList(items);
            renderDetail();
          });
          container.appendChild(button);
        });
      }

      function renderFeatures(items) {
        const container = document.getElementById("feature-grid");
        if (!items.length) {
          container.innerHTML = '<p class="empty-state">--</p>';
          return;
        }
        const getFeatureTier = (value) => {
          if (value >= 78) {
            return { className: "feature-strong", label: "强势" };
          }
          if (value >= 62) {
            return { className: "feature-medium", label: "均衡" };
          }
          return { className: "feature-watch", label: "观察" };
        };
        container.innerHTML = items
          .map((feature) => {
            const tier = getFeatureTier(feature.value);
            return `
              <article class="feature-card ${tier.className}">
                <div>
                  <div class="feature-card-head">
                    <strong>${feature.name}</strong>
                    <span class="feature-chip">${tier.label}</span>
                  </div>
                  <div class="feature-score-row">
                    <span>${feature.value.toFixed(1)}</span>
                    <small class="feature-score-label">score</small>
                  </div>
                  <div class="feature-meter">
                    <div class="feature-meter-fill" style="width: ${Math.max(8, Math.min(feature.value, 100))}%"></div>
                  </div>
                </div>
                <p>${feature.description}</p>
              </article>
            `;
          })
          .join("");
      }

      function splitEvents(items) {
        return {
          official: items.filter((event) => event.source_category === "官方公告"),
          market: items.filter((event) => event.source_category !== "官方公告"),
        };
      }

      function filterEventsByTone(items) {
        if (state.currentEventTone === "all") {
          return items;
        }
        return items.filter((event) => event.sentiment === state.currentEventTone);
      }

      function renderEventTabs(groups) {
        const container = document.getElementById("event-tab-toolbar");
        const tabs = [
          { id: "official", label: `官方公告 ${groups.official.length ? `(${groups.official.length})` : ""}`, disabled: groups.official.length === 0 },
          { id: "market", label: `资讯/研报 ${groups.market.length ? `(${groups.market.length})` : ""}`, disabled: groups.market.length === 0 },
        ];
        container.innerHTML = "";
        tabs.forEach((tab) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = `event-tab-chip${tab.id === state.currentEventTab ? " active" : ""}`;
          button.textContent = tab.label;
          button.disabled = tab.disabled;
          if (!tab.disabled) {
            button.addEventListener("click", () => {
              state.currentEventTab = tab.id;
              renderEvents(getCurrentModePayload()?.stock_details?.[state.currentSymbol]?.recent_events || []);
            });
          }
          container.appendChild(button);
        });
      }

      function renderEventToneFilters(items) {
        const container = document.getElementById("event-tone-toolbar");
        const toneGroups = {
          positive: items.filter((event) => event.sentiment === "positive").length,
          neutral: items.filter((event) => event.sentiment === "neutral").length,
          negative: items.filter((event) => event.sentiment === "negative").length,
        };
        if (state.currentEventTone !== "all" && toneGroups[state.currentEventTone] === 0) {
          state.currentEventTone = "all";
        }
        const tones = [
          { id: "all", label: `全部 (${items.length})`, disabled: items.length === 0 },
          { id: "positive", label: `利好 (${toneGroups.positive})`, disabled: toneGroups.positive === 0 },
          { id: "neutral", label: `中性 (${toneGroups.neutral})`, disabled: toneGroups.neutral === 0 },
          { id: "negative", label: `风险 (${toneGroups.negative})`, disabled: toneGroups.negative === 0 },
        ];
        container.innerHTML = "";
        tones.forEach((tone) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = `event-tone-chip${tone.id === state.currentEventTone ? " active" : ""}`;
          button.textContent = tone.label;
          button.disabled = tone.disabled;
          if (!tone.disabled) {
            button.addEventListener("click", () => {
              state.currentEventTone = tone.id;
              renderEvents(getCurrentModePayload()?.stock_details?.[state.currentSymbol]?.recent_events || []);
            });
          }
          container.appendChild(button);
        });
      }

      function renderEvents(items) {
        const container = document.getElementById("event-list");
        const groups = splitEvents(items);
        if (groups.official.length === 0 && groups.market.length === 0) {
          container.innerHTML = '<p class="empty-state">--</p>';
          document.getElementById("event-tab-toolbar").innerHTML = "";
          document.getElementById("event-tone-toolbar").innerHTML = "";
          return;
        }
        if (state.currentEventTab === "official" && groups.official.length === 0) {
          state.currentEventTab = "market";
        }
        if (state.currentEventTab === "market" && groups.market.length === 0) {
          state.currentEventTab = "official";
        }
        renderEventTabs(groups);
        const currentItems = state.currentEventTab === "official" ? groups.official : groups.market;
        renderEventToneFilters(currentItems);
        const filteredItems = filterEventsByTone(currentItems);
        container.innerHTML = filteredItems.length
          ? filteredItems
              .map(
                (event) => `
                  <article class="event-card sentiment-${event.sentiment || "neutral"}">
                    <div class="event-head">
                      <span>${event.source_category ? `${event.source_category} · ` : ""}${event.source}</span>
                      <span>${formatDateTime(event.publish_time)}</span>
                    </div>
                    <strong>${event.link ? `<a href="${event.link}" target="_blank" rel="noreferrer">${event.title}</a>` : event.title}</strong>
                    <p>${event.summary}</p>
                  </article>
                `,
              )
              .join("")
          : `<p class="empty-state">--</p>`;
      }

      function renderDetailQuickGrid(signal, detail) {
        const container = document.getElementById("detail-quick-grid");
        if (!detail) {
          container.innerHTML = '<p class="empty-state">--</p>';
          return;
        }
        const cards = [
          { label: "证券代码", value: detail.symbol, note: detail.name },
          { label: "所属行业", value: detail.industry, note: "跟随行业主线判断" },
          { label: "模式分", value: signal ? signal.risk_adjusted_score.toFixed(1) : "--", note: signal ? `排名 #${signal.rank}` : "--" },
          { label: "持有窗", value: signal?.holding_window || "--", note: "窗口" },
          { label: "近期事件", value: `${detail.recent_events?.length || 0} 条`, note: "公告 / 资讯 / 研报聚合" },
          { label: "执行偏向", value: detail.risk_plan?.action_bias || "--", note: detail.risk_plan ? detail.risk_plan.price_basis : "--" },
        ];
        container.innerHTML = cards
          .map(
            (card) => `
              <article class="quick-stat-card">
                <span>${card.label}</span>
                <strong>${card.value}</strong>
                <small>${card.note}</small>
              </article>
            `,
          )
          .join("");
      }

      function renderSelectionReasons(signal, detail) {
        const tagContainer = document.getElementById("detail-reason-tags");
        const listContainer = document.getElementById("detail-reason-list");
        const marketContext = document.getElementById("detail-market-context");
        if (!signal || !detail) {
          tagContainer.innerHTML = "<span>--</span>";
          listContainer.innerHTML = '<p class="empty-state">--</p>';
          marketContext.textContent = "";
          return;
        }
        const tags = (signal.event_tags || []).slice(0, 4);
        tagContainer.innerHTML = tags.length
          ? tags.map((tag) => `<span>${tag}</span>`).join("")
          : "<span>--</span>";
        listContainer.innerHTML = (signal.reasons || []).length
          ? signal.reasons
              .map(
                (reason) => `
                  <article class="selection-reason-card">
                    <strong>${reason.label}</strong>
                    <p>${reason.detail}</p>
                  </article>
                `,
              )
              .join("")
          : '<p class="empty-state">--</p>';
        marketContext.textContent = detail.market_context || "";
      }

      function renderDetail() {
        const payload = getCurrentModePayload();
        const detail = payload?.stock_details?.[state.currentSymbol];
        if (!detail) {
          setText("detail-subtitle", "--");
          setText("detail-thesis", "--");
          renderDetailQuickGrid(null, null);
          renderSelectionReasons(null, null);
          renderFeatures([]);
          renderEvents([]);
          return;
        }
        const eventGroups = splitEvents(detail.recent_events || []);
        const signal = (payload?.items || []).find((item) => item.symbol === state.currentSymbol) || null;
        state.currentEventTab = eventGroups.official.length > 0 ? "official" : "market";
        state.currentEventTone = "all";
        setText(
          "detail-subtitle",
          signal
            ? `${detail.name} · ${detail.symbol} · ${detail.industry} · 排名 #${signal.rank}`
            : `${detail.name} · ${detail.symbol} · ${detail.industry}`,
        );
        setText("detail-thesis", detail.thesis);
        renderDetailQuickGrid(signal, detail);
        renderSelectionReasons(signal, detail);
        renderFeatures(detail.feature_scores || []);
        renderEvents(detail.recent_events || []);
      }

      function renderModeSignals() {
        const payload = getCurrentModePayload();
        const items = payload?.items || [];
        state.currentSymbol = items[0]?.symbol || null;
        const modeMeta = (snapshot.mode_summaries || []).find((item) => item.mode_id === state.selectedMode);
        setText(
          "signal-subtitle",
          `${snapshot.trade_date} · ${modeMeta?.display_name || state.selectedMode}`
        );
        setText("signal-count-value", String(Math.min(items.length, 5)));
        renderSignalList(items);
        renderDetail();
      }

      function normalizeHeader(value) {
        return String(value || "").replace(/[\\s_]+/g, "").trim().toLowerCase();
      }

      function detectDelimiter(line) {
        const delimiters = [",", "\\t", ";"];
        let best = ",";
        let bestCount = -1;
        delimiters.forEach((delimiter) => {
          const count = line.split(delimiter).length;
          if (count > bestCount) {
            best = delimiter;
            bestCount = count;
          }
        });
        return best;
      }

      function splitCsvLine(line, delimiter) {
        const cells = [];
        let current = "";
        let inQuotes = false;
        for (let index = 0; index < line.length; index += 1) {
          const char = line[index];
          const next = line[index + 1];
          if (char === '"') {
            if (inQuotes && next === '"') {
              current += '"';
              index += 1;
            } else {
              inQuotes = !inQuotes;
            }
            continue;
          }
          if (char === delimiter && !inQuotes) {
            cells.push(current);
            current = "";
            continue;
          }
          current += char;
        }
        cells.push(current);
        return cells.map((item) => item.trim());
      }

      function parseCsvText(text) {
        const normalizedText = text.replace(/\\r\\n/g, "\\n").replace(/\\r/g, "\\n");
        const lines = normalizedText.split("\\n").filter((line) => line.trim().length > 0);
        if (lines.length < 2) {
          throw new Error("CSV 内容不足，至少需要表头和一行数据。");
        }
        const delimiter = detectDelimiter(lines[0]);
        const headers = splitCsvLine(lines[0], delimiter);
        return lines.slice(1).map((line) => {
          const cells = splitCsvLine(line, delimiter);
          const row = {};
          headers.forEach((header, index) => {
            row[header] = cells[index] || "";
          });
          return row;
        });
      }

      function buildCsvMapping(headers) {
        const normalizedHeaders = {};
        headers.forEach((header) => {
          normalizedHeaders[normalizeHeader(header)] = header;
        });
        const mapping = {};
        Object.entries(CSV_HEADER_ALIASES).forEach(([fieldName, aliases]) => {
          aliases.some((alias) => {
            const match = normalizedHeaders[normalizeHeader(alias)];
            if (match) {
              mapping[fieldName] = match;
              return true;
            }
            return false;
          });
        });
        return mapping;
      }

      function parseNumber(value, fallback = 0) {
        if (value === null || value === undefined || value === "") {
          return fallback;
        }
        const cleaned = String(value).replace(/,/g, "").replace(/[￥¥元股]/g, "").trim();
        const normalized = cleaned.startsWith("(") && cleaned.endsWith(")") ? `-${cleaned.slice(1, -1)}` : cleaned;
        const parsed = Number(normalized);
        return Number.isFinite(parsed) ? parsed : fallback;
      }

      function parseTradeDate(value) {
        const raw = String(value || "").trim();
        if (!raw) {
          throw new Error("missing trade date");
        }
        if (/^\\d{8}$/.test(raw)) {
          return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
        }
        if (raw.includes("/")) {
          return raw.replace(/\\//g, "-").slice(0, 10);
        }
        return raw.slice(0, 10);
      }

      function parseSide(value) {
        const raw = String(value || "").toLowerCase();
        if (["买", "买入", "证券买入", "buy"].some((token) => raw.includes(token))) {
          return "buy";
        }
        if (["卖", "卖出", "证券卖出", "sell"].some((token) => raw.includes(token))) {
          return "sell";
        }
        throw new Error("unsupported side");
      }

      function standardizeTrades(rows, broker) {
        const headers = Object.keys(rows[0] || {});
        const mapping = buildCsvMapping(headers);
        const required = ["trade_date", "symbol", "side", "quantity", "price"];
        const missing = required.filter((field) => !mapping[field]);
        if (missing.length) {
          throw new Error(`文件缺少关键字段映射：${missing.join("、")}`);
        }

        return rows
          .map((row, index) => {
            const tradeDate = parseTradeDate(row[mapping.trade_date]);
            const symbol = String(row[mapping.symbol] || "").replace(/\\D/g, "").slice(-6).padStart(6, "0");
            const side = parseSide(row[mapping.side]);
            const quantity = Math.round(parseNumber(row[mapping.quantity]));
            const price = parseNumber(row[mapping.price]);
            const amount = mapping.amount ? parseNumber(row[mapping.amount], quantity * price) : quantity * price;
            const commission = mapping.commission ? parseNumber(row[mapping.commission]) : 0;
            const stampTax = mapping.stamp_tax ? parseNumber(row[mapping.stamp_tax]) : 0;
            const transferFee = mapping.transfer_fee ? parseNumber(row[mapping.transfer_fee]) : 0;
            const otherFee = mapping.other_fee ? parseNumber(row[mapping.other_fee]) : 0;
            const netAmount = mapping.net_amount
              ? parseNumber(row[mapping.net_amount])
              : (side === "sell" ? amount : -amount) - (commission + stampTax + transferFee + otherFee);
            return {
              trade_date: tradeDate,
              symbol,
              stock_name: mapping.stock_name ? String(row[mapping.stock_name] || "").trim() : symbol,
              side,
              quantity,
              price,
              amount,
              commission,
              stamp_tax: stampTax,
              transfer_fee: transferFee,
              other_fee: otherFee,
              net_amount: netAmount,
              broker,
              raw_row_id: index + 1,
            };
          })
          .filter((trade) => trade.symbol && trade.quantity > 0 && trade.price > 0)
          .sort((a, b) => (a.trade_date < b.trade_date ? -1 : a.trade_date > b.trade_date ? 1 : a.raw_row_id - b.raw_row_id));
      }

      function computeRoundTrips(trades) {
        const positions = {};
        const roundTrips = [];
        trades.forEach((trade) => {
          if (!positions[trade.symbol]) {
            positions[trade.symbol] = [];
          }
          const totalFee = trade.commission + trade.stamp_tax + trade.transfer_fee + trade.other_fee;
          if (trade.side === "buy") {
            positions[trade.symbol].push({
              remainingQty: trade.quantity,
              entryDate: trade.trade_date,
              entryPrice: trade.price,
              feePerShare: totalFee / trade.quantity,
              stockName: trade.stock_name,
            });
            return;
          }

          let remainingSell = trade.quantity;
          const sellFeePerShare = totalFee / trade.quantity;
          while (remainingSell > 0 && positions[trade.symbol].length > 0) {
            const buyLot = positions[trade.symbol][0];
            const matchedQty = Math.min(remainingSell, buyLot.remainingQty);
            const pnl =
              (trade.price - buyLot.entryPrice) * matchedQty -
              (buyLot.feePerShare + sellFeePerShare) * matchedQty;
            const entryCost = buyLot.entryPrice * matchedQty + buyLot.feePerShare * matchedQty;
            const holdingDays = Math.max(
              Math.round((new Date(trade.trade_date) - new Date(buyLot.entryDate)) / (1000 * 60 * 60 * 24)),
              0,
            );
            roundTrips.push({
              symbol: trade.symbol,
              stock_name: buyLot.stockName,
              entry_date: buyLot.entryDate,
              exit_date: trade.trade_date,
              pnl,
              return_pct: entryCost ? pnl / entryCost : 0,
              holding_days: holdingDays,
            });
            buyLot.remainingQty -= matchedQty;
            remainingSell -= matchedQty;
            if (buyLot.remainingQty === 0) {
              positions[trade.symbol].shift();
            }
          }
        });
        return roundTrips;
      }

      function inferTradeStyle(roundTrips, trades) {
        if (!roundTrips.length) {
          return {
            style_id: "unclassified",
            display_name: "待分类",
            confidence: 0.35,
            summary: "当前导入数据还不足以形成完整买卖闭环，建议补充更完整的历史成交。",
            traits: ["建议至少覆盖 3 个月以上交易记录"],
          };
        }
        const averageHolding = roundTrips.reduce((sum, item) => sum + item.holding_days, 0) / roundTrips.length;
        const activeDays = new Set(trades.map((item) => item.trade_date)).size;
        const tradesPerDay = trades.length / Math.max(activeDays, 1);
        if (averageHolding <= 2.5 && tradesPerDay >= 2.2) {
          return {
            style_id: "high_frequency_short",
            display_name: "高频短线型",
            confidence: 0.79,
            summary: "交易节奏偏快，更像短线试错和快速切换，对执行纪律要求很高。",
            traits: ["出手频率高", "更吃执行纪律", "手续费侵蚀需要重点控制"],
          };
        }
        if (averageHolding <= 8) {
          return {
            style_id: "swing_short",
            display_name: "短波段交易型",
            confidence: 0.82,
            summary: "盈利更像来自 3 到 8 天的顺势波段，适合围绕主线做确认后的跟随。",
            traits: ["偏顺势而为", "适合板块共振时参与", "不宜高频冲动换股"],
          };
        }
        return {
          style_id: "trend_hold",
          display_name: "耐心波段型",
          confidence: 0.74,
          summary: "持仓更愿意跨越多个交易日等待趋势展开，风格偏中短趋势而非短线博弈。",
          traits: ["更依赖趋势结构", "适合减少高频换股", "应强化止损与加仓规则"],
        };
      }

      function formatSignedPercent(value) {
        const percent = (value * 100).toFixed(1);
        return `${value > 0 ? "+" : ""}${percent}%`;
      }

      function buildTradeDiagnostics(trades, broker, filename) {
        const roundTrips = computeRoundTrips(trades);
        const styleProfile = inferTradeStyle(roundTrips, trades);
        const wins = roundTrips.filter((item) => item.pnl > 0);
        const losses = roundTrips.filter((item) => item.pnl <= 0);
        const grossProfit = wins.reduce((sum, item) => sum + item.pnl, 0);
        const grossLoss = Math.abs(losses.reduce((sum, item) => sum + item.pnl, 0));
        const avgHolding = roundTrips.length
          ? roundTrips.reduce((sum, item) => sum + item.holding_days, 0) / roundTrips.length
          : 0;
        const winRate = roundTrips.length ? wins.length / roundTrips.length : 0;
        const avgWinPct = wins.length ? wins.reduce((sum, item) => sum + item.return_pct, 0) / wins.length : 0;
        const avgLossPct = losses.length ? losses.reduce((sum, item) => sum + item.return_pct, 0) / losses.length : 0;
        const profitFactor = grossLoss ? grossProfit / grossLoss : grossProfit;
        const winningHold = wins.length ? wins.reduce((sum, item) => sum + item.holding_days, 0) / wins.length : 0;
        const losingHold = losses.length ? losses.reduce((sum, item) => sum + item.holding_days, 0) / losses.length : 0;
        const buyCount = trades.filter((item) => item.side === "buy").length;
        const sellCount = trades.filter((item) => item.side === "sell").length;
        const multiBuyRatio = buyCount / Math.max(sellCount, 1);

        const errorPatterns = [];
        const effectivePatterns = [];
        const recommendations = [];

        if (avgWinPct < Math.abs(avgLossPct)) {
          errorPatterns.push({
            title: "赚小亏大倾向",
            detail: "平均盈利幅度仍小于平均亏损幅度，说明止盈偏早或止损偏慢。",
            severity: "high",
          });
          recommendations.push("把第一止盈设置得更客观一些，避免盈利单过早离场。");
        }
        if (losingHold > winningHold * 1.25 && losingHold >= 3) {
          errorPatterns.push({
            title: "亏损单持有偏久",
            detail: "亏损交易比盈利交易更久，说明容易在逻辑失效后继续拖单。",
            severity: "high",
          });
          recommendations.push("把跌破关键均线或事件失效作为硬性离场条件。");
        }
        if (multiBuyRatio > 1.35) {
          errorPatterns.push({
            title: "补仓摊薄使用偏多",
            detail: "买入次数相对卖出次数偏高，说明更常通过加仓摊低成本来处理亏损单。",
            severity: "medium",
          });
          recommendations.push("只有在逻辑被二次确认时才允许加仓，避免用补仓替代认错。");
        }

        if (profitFactor >= 1.3) {
          effectivePatterns.push({
            title: "收益质量仍有基础",
            detail: "总盈利与总亏损比值保持在可优化区间，说明问题更多在纪律，而不是策略完全失效。",
            severity: "positive",
          });
        }
        if (winningHold >= 3 && winningHold > losingHold) {
          effectivePatterns.push({
            title: "盈利单拿得住",
            detail: "赚钱的交易能获得更长持有周期，这说明顺势持有对你有效。",
            severity: "positive",
          });
          recommendations.push("优先保留 3 到 8 天的趋势延续型交易，减少低质量频繁试错。");
        }
        if (winRate < 0.45) {
          recommendations.push("把交易触发条件再收紧一档，只做主线行业与事件共振更明确的机会。");
        } else {
          recommendations.push("继续围绕高胜率场景建立清单，避免偏离最有效的交易模板。");
        }

        const tradeDates = trades.map((item) => item.trade_date).sort();
        const batch = {
          batch_id: `offline-${Date.now()}`,
          imported_at: new Date().toISOString(),
          broker,
          source_type: "offline_csv",
          filename,
          detected_format: "csv",
          row_count: trades.length,
          imported_count: trades.length,
          ignored_count: 0,
          symbol_count: new Set(trades.map((item) => item.symbol)).size,
          start_date: tradeDates[0],
          end_date: tradeDates[tradeDates.length - 1],
          notes: "离线 HTML 本地解析结果，仅在当前页面有效。",
        };

        return {
          status: "offline_live",
          account_label: `${broker} 本地导入结果`,
          coverage_text: `已在离线页面解析 ${trades.length} 条成交记录，覆盖 ${batch.start_date} 至 ${batch.end_date}。`,
          latest_batch: batch,
          summary_metrics: [
            { label: "闭环交易数", value: String(roundTrips.length), detail: "按 FIFO 方式配对后的完整买卖记录。" },
            { label: "胜率", value: formatPercent(winRate), detail: "盈利交易在全部闭环交易中的占比。" },
            { label: "盈亏比", value: Number.isFinite(profitFactor) ? profitFactor.toFixed(2) : "--", detail: "总盈利 / 总亏损，越高越稳。" },
            { label: "平均持仓", value: `${avgHolding.toFixed(1)} 天`, detail: "帮助判断你更适合短线、波段还是趋势持有。" },
          ],
          style_profile: styleProfile,
          win_loss_comparison: [
            { label: "盈利单平均持有", value: `${winningHold.toFixed(1)} 天`, detail: "赚钱时能否拿住，决定你的上沿收益。" },
            { label: "亏损单平均持有", value: `${losingHold.toFixed(1)} 天`, detail: "亏损持有过久通常意味着离场纪律不足。" },
            { label: "盈利单平均收益", value: formatSignedPercent(avgWinPct), detail: "观察赚钱交易的典型回报区间。" },
            { label: "亏损单平均回撤", value: formatSignedPercent(avgLossPct), detail: "帮助判断是否经常陷入赚小亏大。" },
          ],
          error_patterns: errorPatterns.slice(0, 3),
          effective_patterns: effectivePatterns.slice(0, 3),
          recommendations: recommendations.slice(0, 4),
          recent_batches: [batch],
        };
      }

      function renderTradeProfiles() {
        const select = document.getElementById("trade-profile-select");
        select.innerHTML = "";
        state.tradeProfiles.forEach((profile) => {
          const option = document.createElement("option");
          option.value = profile.profile_id;
          option.textContent = `${profile.display_name} · ${profile.recommended_format}`;
          select.appendChild(option);
        });
        select.addEventListener("change", () => renderTradeGuide(select.value));
        if (state.tradeProfiles.length) {
          renderTradeGuide(state.tradeProfiles[0].profile_id);
        }

        const fieldGrid = document.getElementById("trade-field-grid");
        fieldGrid.innerHTML = state.tradeStandardFields
          .map(
            (field) => `
              <article class="field-card">
                <div class="event-head">
                  <span>${field.display_name}</span>
                  <span>${field.required ? "必填" : "可选"}</span>
                </div>
                <strong>${field.field_name}</strong>
                <p>${field.description}</p>
              </article>
            `,
          )
          .join("");
      }

      function renderTradeGuide(profileId) {
        const container = document.getElementById("trade-profile-guide");
        const profile = state.tradeProfiles.find((item) => item.profile_id === profileId);
        if (!profile) {
          container.innerHTML = '<p class="empty-state">未找到模板说明。</p>';
          return;
        }
        container.innerHTML = `
          <article class="guide-card">
            <strong>${profile.display_name}</strong>
            <p>${profile.description}</p>
            <div class="tag-row">
              <span>${profile.broker}</span>
              <span>${profile.recommended_format}</span>
              <span>${profile.supported_extensions.join(" / ")}</span>
            </div>
            <ol class="guide-list">${(profile.export_steps || []).map((item) => `<li>${item}</li>`).join("")}</ol>
          </article>
        `;
      }

      function renderTradeSidebarSummary(payload) {
        const container = document.getElementById("trade-sidebar-summary");
        if (!container) {
          return;
        }
        const chips = [];
        if (payload?.style_profile?.display_name) {
          chips.push({ text: payload.style_profile.display_name, primary: true });
        }
        if (payload?.summary_metrics?.[0]?.value) {
          chips.push({ text: `${payload.summary_metrics[0].label} ${payload.summary_metrics[0].value}` });
        }
        if (payload?.summary_metrics?.[1]?.value) {
          chips.push({ text: `${payload.summary_metrics[1].label} ${payload.summary_metrics[1].value}` });
        }
        if (payload?.latest_batch?.imported_count) {
          chips.push({ text: `最近导入 ${payload.latest_batch.imported_count} 条` });
        } else if (payload?.status === "demo") {
          chips.push({ text: "当前示例诊断" });
        }
        container.innerHTML = chips.length
          ? chips
              .map(
                (item) =>
                  `<span class="trade-summary-chip${item.primary ? " primary" : ""}">${item.text}</span>`,
              )
              .join("")
          : '<p class="empty-state">暂无诊断概览。</p>';
      }

      function renderTradeDiagnostics(payload) {
        state.tradeDiagnostics = payload;
        setText("trade-coverage-text", payload.coverage_text || "暂无交易诊断。");
        renderTradeSidebarSummary(payload);

        const styleCard = document.getElementById("trade-style-card");
        const style = payload.style_profile || {};
        styleCard.innerHTML = `
          <div class="style-title-row">
            <strong>${style.display_name || "待分类"}</strong>
            <span>${style.confidence !== undefined ? formatPercent(style.confidence) : "--"}</span>
          </div>
          <p>${style.summary || "当前暂无风格画像。"}</p>
          <div class="tag-row">${(style.traits || []).map((item) => `<span>${item}</span>`).join("")}</div>
        `;

        const summaryGrid = document.getElementById("trade-summary-grid");
        summaryGrid.innerHTML = (payload.summary_metrics || [])
          .map((item) => `<article class="trade-card"><strong>${item.label}</strong><span>${item.value}</span><p>${item.detail}</p></article>`)
          .join("");

        const compareGrid = document.getElementById("trade-compare-grid");
        compareGrid.innerHTML = (payload.win_loss_comparison || [])
          .map((item) => `<article class="trade-card"><strong>${item.label}</strong><span>${item.value}</span><p>${item.detail}</p></article>`)
          .join("");

        const errorList = document.getElementById("trade-error-list");
        errorList.innerHTML = (payload.error_patterns || []).length
          ? payload.error_patterns
              .map(
                (item) => `<article class="trade-insight-card negative"><div class="event-head"><span>错误模式</span><span>${item.severity}</span></div><strong>${item.title}</strong><p>${item.detail}</p></article>`,
              )
              .join("")
          : '<p class="empty-state">当前没有明显错误模式。</p>';

        const effectiveList = document.getElementById("trade-effective-list");
        effectiveList.innerHTML = (payload.effective_patterns || []).length
          ? payload.effective_patterns
              .map(
                (item) => `<article class="trade-insight-card positive"><div class="event-head"><span>有效模式</span><span>${item.severity}</span></div><strong>${item.title}</strong><p>${item.detail}</p></article>`,
              )
              .join("")
          : '<p class="empty-state">当前还没有明显有效模式总结。</p>';

        const recommendationList = document.getElementById("trade-recommendation-list");
        recommendationList.innerHTML = (payload.recommendations || []).length
          ? payload.recommendations.map((item) => `<li>${item}</li>`).join("")
          : "<li>暂无优化建议。</li>";

        const batchList = document.getElementById("trade-batch-list");
        batchList.innerHTML = (payload.recent_batches || []).length
          ? payload.recent_batches
              .map(
                (batch) => `
                  <article class="batch-card">
                    <div class="event-head">
                      <span>${batch.broker}</span>
                      <span>${batch.imported_at ? formatDateTime(batch.imported_at) : "--"}</span>
                    </div>
                    <strong>${batch.filename}</strong>
                    <p>${batch.imported_count} 条记录 · ${batch.symbol_count} 只股票 · ${String(batch.source_type || "").toUpperCase()}</p>
                  </article>
                `,
              )
              .join("")
          : '<p class="empty-state">暂无最近批次记录。</p>';
      }

      function setupTradeImport() {
        const form = document.getElementById("trade-import-form");
        const fileInput = document.getElementById("trade-file-input");
        const select = document.getElementById("trade-profile-select");
        const status = document.getElementById("trade-import-status");
        const button = document.getElementById("trade-import-button");
        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          const file = fileInput.files?.[0];
          if (!file) {
            status.textContent = "请先选择一个导出的交易文件。";
            return;
          }
          if (!file.name.toLowerCase().endsWith(".csv") && !file.name.toLowerCase().endsWith(".txt")) {
            status.textContent = "离线 HTML 当前只支持 CSV 即时解析；如需 XLSX，请使用在线版。";
            return;
          }
          button.disabled = true;
          button.textContent = "解析中...";
          try {
            const text = await file.text();
            const rows = parseCsvText(text);
            const profile = state.tradeProfiles.find((item) => item.profile_id === select.value);
            const trades = standardizeTrades(rows, profile?.broker || "离线导入");
            const diagnostics = buildTradeDiagnostics(trades, profile?.broker || "离线导入", file.name);
            renderTradeDiagnostics(diagnostics);
            status.textContent = `本地解析完成：${trades.length} 条成交记录，诊断已刷新。`;
          } catch (error) {
            status.textContent = error instanceof Error ? error.message : "本地解析失败，请检查文件格式。";
          } finally {
            button.disabled = false;
            button.textContent = "本地解析并刷新诊断";
          }
        });
      }

      function setupAiModal() {
        const button = document.getElementById("refresh-ai-risk-button");
        const closeButton = document.getElementById("ai-analysis-close");
        const backdrop = document.getElementById("ai-analysis-backdrop");
        const modal = document.getElementById("ai-analysis-modal");

        if (button) {
          button.disabled = false;
          button.addEventListener("click", () => {
            const payload = getCurrentModePayload();
            const detail = payload?.stock_details?.[state.currentSymbol];
            openAiAnalysisModal(detail?.ai_risk_analysis || null);
          });
        }
        if (closeButton) {
          closeButton.addEventListener("click", closeAiAnalysisModal);
        }
        if (backdrop) {
          backdrop.addEventListener("click", closeAiAnalysisModal);
        }
        document.addEventListener("keydown", (event) => {
          if (event.key === "Escape" && modal && !modal.classList.contains("is-hidden")) {
            closeAiAnalysisModal();
          }
        });
      }

      function bootstrapSelector() {
        renderMarketSentiment();
        setText("exposure-value", marketPayload.suggested_exposure !== undefined ? formatPercent(marketPayload.suggested_exposure) : "--");
        setText("sector-count-value", String((snapshot.top_sectors || []).length));

        renderSectors(snapshot.top_sectors || []);
        renderModeToolbar();
        renderModeSummary();
        renderModeSignals();
      }

      function bootstrapDiagnostics() {
        renderTradeProfiles();
        renderTradeDiagnostics(initialDiagnostics);
        setupTradeImport();
      }

      window.addEventListener("DOMContentLoaded", () => {
        setupViewTabs();
        setupAiModal();
        renderViewTabs();
        bootstrapSelector();
        bootstrapDiagnostics();
      });
    </script>
  </body>
</html>
"""


def render_preview_html(snapshot: dict, output_path: Path) -> None:
    existing_index = output_path if output_path.exists() else Path(__file__).resolve().parents[2] / "index.html"
    existing_text = existing_index.read_text(encoding="utf-8")
    style_start = existing_text.find("<style>")
    style_end = existing_text.find("</style>", style_start + 7)
    if style_start == -1 or style_end == -1:
        raise FileNotFoundError("Unable to locate embedded CSS source for index.html generation.")
    embedded_css = existing_text[style_start + len("<style>") : style_end].strip("\n")
    merged_snapshot = merge_cached_ai_analysis(snapshot, output_path)
    market_payload = load_market_preview_payload(merged_snapshot)
    trade_profiles_payload, trade_diagnostics_payload = load_trade_preview_payload()

    html = (
        TEMPLATE.replace("__EMBEDDED_CSS__", embedded_css)
        .replace("__SNAPSHOT_JSON__", json.dumps(merged_snapshot, ensure_ascii=False))
        .replace("__MARKET_PAYLOAD_JSON__", json.dumps(market_payload, ensure_ascii=False))
        .replace("__TRADE_PROFILES_JSON__", json.dumps(trade_profiles_payload, ensure_ascii=False))
        .replace("__TRADE_DIAGNOSTICS_JSON__", json.dumps(trade_diagnostics_payload, ensure_ascii=False))
    )
    output_path.write_text(html, encoding="utf-8")
