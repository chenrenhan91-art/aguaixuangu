from datetime import date, datetime, timedelta, timezone

from app.models.domain import (
    CandidateSignal,
    EquityCurvePoint,
    MarketRegimeSnapshot,
    NewsEventRecord,
    SectorRanking,
    StockResearchBrief,
    TradeRecord,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def demo_market_regime() -> MarketRegimeSnapshot:
    return MarketRegimeSnapshot(
        regime="risk_on",
        confidence=0.74,
        suggested_exposure=0.68,
        breadth_score=73.0,
        northbound_score=66.0,
        momentum_score=79.0,
        updated_at=now_utc(),
    )


def demo_top_sectors() -> list[SectorRanking]:
    return [
        SectorRanking("AI_INFRA", "AI 算力", 92.0, 94.0, 88.0, 90.0),
        SectorRanking("SEMI", "半导体设备", 88.0, 86.0, 85.0, 84.0),
        SectorRanking("POWER", "电力设备", 84.0, 81.0, 82.0, 80.0),
        SectorRanking("AUTO", "智能汽车", 82.0, 79.0, 83.0, 78.0),
        SectorRanking("SOFT", "工业软件", 80.0, 77.0, 79.0, 81.0),
        SectorRanking("MEDTECH", "医疗器械", 76.0, 72.0, 75.0, 70.0),
    ]


def demo_signals() -> list[CandidateSignal]:
    return [
        CandidateSignal(
            symbol="000977.SZ",
            name="浪潮信息",
            industry="AI 算力",
            rank=1,
            base_score=88.0,
            event_score=74.0,
            risk_adjusted_score=86.0,
            holding_window="3-5D",
            reasons=[
                ("行业强度", "AI 算力位于行业轮动前列，强度评分连续 5 个交易日维持高位。"),
                ("价格结构", "20 日线上方运行，近 5 日放量突破平台。"),
                ("事件增强", "算力链订单预期抬升，新闻热度和关联度同步提升。"),
            ],
            event_tags=["算力订单", "北向回流"],
        ),
        CandidateSignal(
            symbol="603019.SH",
            name="中科曙光",
            industry="AI 算力",
            rank=2,
            base_score=85.0,
            event_score=70.0,
            risk_adjusted_score=83.0,
            holding_window="3-5D",
            reasons=[
                ("板块共振", "与算力主线同频共振，板块内部排序靠前。"),
                ("量价配合", "换手率处于近 60 日高分位，放量但不过热。"),
                ("风险控制", "波动率可控，ATR 止损空间清晰。"),
            ],
            event_tags=["国资云", "自主算力"],
        ),
        CandidateSignal(
            symbol="300308.SZ",
            name="中际旭创",
            industry="光模块",
            rank=3,
            base_score=82.0,
            event_score=69.0,
            risk_adjusted_score=80.0,
            holding_window="3-5D",
            reasons=[
                ("趋势保持", "均线多头排列未破坏，中期趋势延续。"),
                ("相对强弱", "相对沪深 300 超额收益持续走强。"),
                ("事件过滤", "新闻偏利好但未出现过热叙事。"),
            ],
            event_tags=["光模块", "业绩预期"],
        ),
        CandidateSignal(
            symbol="002371.SZ",
            name="北方华创",
            industry="半导体设备",
            rank=4,
            base_score=80.0,
            event_score=65.0,
            risk_adjusted_score=78.0,
            holding_window="5D",
            reasons=[
                ("行业轮动", "半导体设备强度回升，行业过滤通过。"),
                ("突破确认", "突破前高后缩量整理，结构健康。"),
                ("资金质量", "成交额放大但未显著背离。"),
            ],
            event_tags=["设备国产化"],
        ),
        CandidateSignal(
            symbol="300124.SZ",
            name="汇川技术",
            industry="工业自动化",
            rank=5,
            base_score=78.0,
            event_score=61.0,
            risk_adjusted_score=76.0,
            holding_window="5D",
            reasons=[
                ("基本面稳健", "趋势和波动结构更适合中短持有。"),
                ("板块修复", "工业软件和自动化板块同步修复。"),
                ("回撤友好", "近阶段最大单日波动相对可控。"),
            ],
            event_tags=["自动化", "制造升级"],
        ),
    ]


def demo_stock_briefs() -> dict[str, StockResearchBrief]:
    events_primary = [
        NewsEventRecord(
            event_id="evt-001",
            title="算力基础设施需求提升，服务器产业链关注度回升",
            publish_time=now_utc() - timedelta(hours=6),
            source="财联社",
            event_type="产业新闻",
            sentiment="positive",
            impact_level="high",
            summary="产业链新闻强化了 AI 算力方向的景气预期，但更适合作为趋势确认，而不是单独买入依据。",
        ),
        NewsEventRecord(
            event_id="evt-002",
            title="北向资金回流科技主线",
            publish_time=now_utc() - timedelta(hours=2),
            source="上证报",
            event_type="资金面",
            sentiment="positive",
            impact_level="medium",
            summary="北向资金回流有助于提高市场风格的持续性，对龙头个股形成边际强化。",
        ),
    ]

    return {
        "000977.SZ": StockResearchBrief(
            symbol="000977.SZ",
            name="浪潮信息",
            industry="AI 算力",
            thesis="行业主线明确，量价结构健康，适合纳入 3 到 5 日持有窗口的候选池。",
            market_context="当前市场状态偏 risk_on，科技主线获得行业轮动和资金回流双重支撑。",
            feature_scores=[
                ("行业强度", 92.0, "AI 算力位居行业轮动榜首。"),
                ("趋势延续", 87.0, "20 日和 60 日趋势方向一致。"),
                ("放量质量", 81.0, "放量突破但未出现极端过热。"),
                ("事件确认", 74.0, "新闻增强有效，但未超过结构信号权重。"),
            ],
            recent_events=events_primary,
            risk_controls=[
                "单票仓位建议不超过组合净值的 12%。",
                "若跌破 5 日线且成交额同步放大，优先降仓。",
                "若市场状态从 risk_on 切换到 neutral，降低预期持仓天数。",
            ],
        ),
        "603019.SH": StockResearchBrief(
            symbol="603019.SH",
            name="中科曙光",
            industry="AI 算力",
            thesis="行业共振较强，趋势与事件方向一致，适合做龙头池中的备选标的。",
            market_context="算力主线保持景气，市场风格仍偏成长，适合中短线顺势配置。",
            feature_scores=[
                ("行业强度", 90.0, "板块排名居前，且板块内部排序稳定。"),
                ("相对强弱", 84.0, "对宽基和行业基准均保持超额。"),
                ("波动控制", 79.0, "ATR 范围仍在可控区间。"),
                ("事件确认", 70.0, "自主算力主题强化了研究逻辑。"),
            ],
            recent_events=events_primary,
            risk_controls=[
                "关注放量长上影，避免追高后回落。",
                "若 2 个交易日内未形成新高，考虑降低排序优先级。",
            ],
        ),
        "300308.SZ": StockResearchBrief(
            symbol="300308.SZ",
            name="中际旭创",
            industry="光模块",
            thesis="更适合作为趋势跟随型标的，胜在趋势顺滑而非事件驱动。",
            market_context="成长风格占优，但需要警惕高位趋势股的波动放大。",
            feature_scores=[
                ("趋势延续", 86.0, "均线结构完整，趋势未破坏。"),
                ("收益质量", 80.0, "超额收益主要来自持续上行，而非单日脉冲。"),
                ("事件热度", 69.0, "利好存在，但并非最强催化主线。"),
            ],
            recent_events=events_primary[:1],
            risk_controls=[
                "更适合分批建仓，不建议一次性满仓追高。",
                "若跌破关键趋势线，优先执行止盈止损纪律。",
            ],
        ),
        "002371.SZ": StockResearchBrief(
            symbol="002371.SZ",
            name="北方华创",
            industry="半导体设备",
            thesis="适合作为行业轮动扩散阶段的延展配置，信号强度略弱于算力主线。",
            market_context="半导体设备处于回暖早期，更适合观察确认后的参与。",
            feature_scores=[
                ("行业轮动", 84.0, "行业得分稳步抬升。"),
                ("突破确认", 78.0, "平台突破后回踩结构尚可。"),
                ("事件热度", 65.0, "国产替代叙事形成支撑。"),
            ],
            recent_events=events_primary[:1],
            risk_controls=[
                "若行业轮动排名掉出前五，降低仓位权重。",
            ],
        ),
        "300124.SZ": StockResearchBrief(
            symbol="300124.SZ",
            name="汇川技术",
            industry="工业自动化",
            thesis="偏防守型进攻标的，适合平衡组合波动。",
            market_context="行业修复中，方向明确但弹性相对温和。",
            feature_scores=[
                ("稳健度", 82.0, "回撤特征优于高弹性题材股。"),
                ("行业热度", 73.0, "板块处于中高位但非核心主线。"),
                ("事件确认", 61.0, "政策和产业叙事更多是辅助。"),
            ],
            recent_events=events_primary[:1],
            risk_controls=[
                "更适合组合平衡，不建议作为第一仓位核心。",
            ],
        ),
    }


def demo_equity_curve() -> list[EquityCurvePoint]:
    base_day = date.today() - timedelta(days=9)
    values = [1.00, 1.02, 1.01, 1.04, 1.06, 1.05, 1.08, 1.10, 1.09, 1.12]
    drawdowns = [0.00, 0.00, -0.01, 0.00, 0.00, -0.01, 0.00, 0.00, -0.01, 0.00]
    curve: list[EquityCurvePoint] = []
    for index, value in enumerate(values):
        curve.append(
            EquityCurvePoint(
                trade_date=base_day + timedelta(days=index),
                equity=round(value, 4),
                drawdown=round(drawdowns[index], 4),
            )
        )
    return curve


def demo_trades() -> list[TradeRecord]:
    return [
        TradeRecord("000977.SZ", "浪潮信息", date.today() - timedelta(days=8), date.today() - timedelta(days=4), 39.8, 43.5, 0.0930, 4),
        TradeRecord("603019.SH", "中科曙光", date.today() - timedelta(days=7), date.today() - timedelta(days=3), 51.2, 54.1, 0.0566, 4),
        TradeRecord("300308.SZ", "中际旭创", date.today() - timedelta(days=6), date.today() - timedelta(days=1), 112.4, 118.0, 0.0498, 5),
        TradeRecord("300124.SZ", "汇川技术", date.today() - timedelta(days=5), date.today() - timedelta(days=2), 62.5, 64.0, 0.0240, 3),
    ]

