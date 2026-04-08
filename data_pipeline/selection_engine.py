from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Optional

import pandas as pd

from data_pipeline.adapters.akshare_market import AKShareMarketDataAdapter


POSITIVE_KEYWORDS = {
    "业绩预告": 18,
    "预盈": 18,
    "扭亏": 18,
    "中标": 16,
    "订单": 14,
    "签约": 12,
    "合作": 10,
    "回购": 12,
    "增持": 10,
    "预增": 16,
    "增长": 8,
    "液冷": 8,
    "算力": 10,
    "服务器": 8,
    "芯片": 10,
    "AI": 8,
    "新品": 8,
    "扩产": 10,
    "获批": 12,
    "主力资金": 6,
}

NEGATIVE_KEYWORDS = {
    "减持": -15,
    "预减": -16,
    "亏损": -18,
    "下滑": -10,
    "风险提示": -12,
    "处罚": -18,
    "问询": -10,
    "诉讼": -10,
    "终止": -14,
    "冻结": -10,
    "减值": -12,
    "跌停": -10,
    "净流出": -6,
}

LOW_SIGNAL_KEYWORDS = {"互动平台", "投资者提问", "股东户数", "答复", "e公司讯"}
ANNOUNCEMENT_NOISE_KEYWORDS = {"法律意见书", "股东会", "监事会", "董事会", "章程", "自查报告"}

EVENT_TYPE_RULES = {
    "订单合作": ["中标", "订单", "签约", "合作", "采购", "供货", "交流会"],
    "业绩财报": ["业绩", "净利润", "营收", "预增", "预减", "年报", "季报"],
    "产品技术": ["AI", "算力", "服务器", "芯片", "液冷", "模型", "新品"],
    "资金交易": ["主力资金", "回购", "增持", "减持", "龙虎榜"],
    "政策行业": ["政策", "工信部", "商务部", "发改委", "补贴", "规划"],
    "风险监管": ["处罚", "问询", "风险提示", "诉讼", "终止"],
}

SOURCE_BONUS = {
    "证券时报": 3,
    "证券时报网": 3,
    "证券日报": 3,
    "中国证券报·中证网": 3,
    "中国证券报": 3,
    "界面新闻": 2,
    "上证报": 3,
    "财联社": 3,
    "巨潮资讯": 6,
    "东方财富研报": 4,
}


@dataclass(frozen=True)
class SelectionConfig:
    top_industry_count: int = 5
    stocks_per_industry: int = 6
    preliminary_candidate_count: int = 18
    final_candidate_count: int = 5
    min_turnover_rate: float = 1.0
    min_amount: float = 150_000_000.0
    min_history_days: int = 60


@dataclass(frozen=True)
class StrategyModeDefinition:
    mode_id: str
    display_name: str
    description: str
    holding_window: str
    score_weights: dict[str, float]
    preferred_features: list[str] = field(default_factory=list)


STRATEGY_MODES: tuple[StrategyModeDefinition, ...] = (
    StrategyModeDefinition(
        mode_id="balanced",
        display_name="综合研判",
        description="行业轮动、技术结构、新闻事件和短线热度均衡打分，适合作为默认模式。",
        holding_window="3-5D",
        score_weights={"industry": 0.28, "technical": 0.32, "event": 0.2, "sentiment": 0.2},
        preferred_features=["行业轮动", "技术趋势", "新闻催化", "情绪热度"],
    ),
    StrategyModeDefinition(
        mode_id="sector_rotation",
        display_name="行业轮动优先",
        description="优先锁定强势行业中最具代表性的龙头和跟涨标的，适合主线行情。",
        holding_window="2-4D",
        score_weights={"industry": 0.42, "technical": 0.28, "event": 0.12, "sentiment": 0.18},
        preferred_features=["行业强度", "资金共识", "龙头扩散"],
    ),
    StrategyModeDefinition(
        mode_id="event_driven",
        display_name="消息事件驱动",
        description="提高新闻催化和政策事件的权重，适合盘前筛选消息面机会。",
        holding_window="1-3D",
        score_weights={"industry": 0.2, "technical": 0.18, "event": 0.44, "sentiment": 0.18},
        preferred_features=["事件催化", "政策新闻", "公告情绪"],
    ),
    StrategyModeDefinition(
        mode_id="trend_breakout",
        display_name="技术趋势突破",
        description="突出均线趋势、放量和突破强度，适合波段跟踪和趋势确认。",
        holding_window="5-10D",
        score_weights={"industry": 0.2, "technical": 0.5, "event": 0.1, "sentiment": 0.2},
        preferred_features=["均线多头", "放量突破", "趋势延续"],
    ),
    StrategyModeDefinition(
        mode_id="short_term_relay",
        display_name="短线情绪接力",
        description="用日线涨速、换手和量比近似短线情绪强度，适合次日强势跟踪。",
        holding_window="1-2D",
        score_weights={"industry": 0.16, "technical": 0.22, "event": 0.08, "sentiment": 0.54},
        preferred_features=["涨幅强度", "换手接力", "资金活跃度"],
    ),
)

MODE_INDEX = {mode.mode_id: mode for mode in STRATEGY_MODES}
DEFAULT_MODE_ID = "balanced"


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def pct_change(new_value: float, old_value: float) -> float:
    if old_value == 0:
        return 0.0
    return (new_value - old_value) / old_value


def classify_event_type(text: str) -> str:
    for event_type, keywords in EVENT_TYPE_RULES.items():
        if any(keyword in text for keyword in keywords):
            return event_type
    return "其他"


def normalize_stock_name(name: str) -> str:
    return "".join(str(name).split())


def build_stock_aliases(stock_name: str, symbol: str) -> set[str]:
    aliases = {stock_name, normalize_stock_name(stock_name), symbol, symbol[-6:]}
    cleaned_name = stock_name.replace("*", "").replace("ST", "").replace("st", "")
    aliases.add(cleaned_name)
    aliases.add(normalize_stock_name(cleaned_name))
    return {alias for alias in aliases if alias}


def classify_event_type_with_source(text: str, source_category: str) -> str:
    if source_category == "官方公告":
        return "官方公告"
    if source_category == "券商研报":
        return "券商研报"
    return classify_event_type(text)


def is_relevant_stock_event(stock_name: str, symbol: str, row: pd.Series) -> bool:
    source_category = str(row.get("来源类别", ""))
    match_type = str(row.get("匹配类型", ""))
    if match_type == "exact_symbol" or source_category in {"官方公告", "券商研报"}:
        return True

    text = f"{row.get('新闻标题', '')} {row.get('新闻内容', '')}"
    normalized_text = normalize_stock_name(text)
    aliases = build_stock_aliases(stock_name=stock_name, symbol=symbol)
    return any(alias in text or alias in normalized_text for alias in aliases)


def score_industries(df: pd.DataFrame) -> pd.DataFrame:
    scored = df.copy()
    for column in [
        "涨跌幅",
        "上涨家数",
        "下跌家数",
        "领涨股票-涨跌幅",
        "总成交额",
        "净流入",
        "换手率",
    ]:
        if column not in scored.columns:
            scored[column] = 0.0
        scored[column] = pd.to_numeric(scored[column], errors="coerce").fillna(0.0)

    total_count = (scored["上涨家数"] + scored["下跌家数"]).replace(0, 1)
    scored["breadth_ratio"] = scored["上涨家数"] / total_count

    amount_proxy = scored["总成交额"] / 100 if "总成交额" in scored.columns else 0.0
    capital_proxy = scored["净流入"] if "净流入" in scored.columns else scored["换手率"] * 2.0

    scored["strength_score"] = (
        44
        + scored["涨跌幅"].clip(-5, 10) * 4
        + scored["breadth_ratio"] * 22
        + capital_proxy.clip(-12, 18) * 1.2
    ).clip(0, 100)
    scored["momentum_score"] = (
        46
        + scored["涨跌幅"].clip(-5, 10) * 4.6
        + scored["领涨股票-涨跌幅"].clip(-10, 20) * 1.4
    ).clip(0, 100)
    scored["heat_score"] = (
        42
        + scored["上涨家数"].clip(0, 60) * 0.45
        - scored["下跌家数"].clip(0, 60) * 0.18
        + amount_proxy.clip(0, 200) * 0.22
    ).clip(0, 100)
    scored["capital_consensus_score"] = (
        40
        + amount_proxy.clip(0, 200) * 0.24
        + capital_proxy.clip(-12, 18) * 1.5
        + scored["breadth_ratio"] * 12
    ).clip(0, 100)
    scored["sector_score"] = (
        0.34 * scored["strength_score"]
        + 0.28 * scored["momentum_score"]
        + 0.2 * scored["heat_score"]
        + 0.18 * scored["capital_consensus_score"]
    )
    scored.sort_values("sector_score", ascending=False, inplace=True)
    return scored.reset_index(drop=True)


def compute_stock_features(hist_df: pd.DataFrame) -> Optional[dict[str, float]]:
    if hist_df is None or hist_df.empty or len(hist_df) < 60:
        return None

    closes = hist_df["收盘"].astype(float).tolist()
    amounts = hist_df["成交额"].astype(float).tolist()
    turnovers = hist_df["换手率"].astype(float).tolist()
    pct_values = hist_df["涨跌幅"].astype(float).tolist()
    highs = hist_df["最高"].astype(float).tolist()
    lows = hist_df["最低"].astype(float).tolist()

    latest_close = closes[-1]
    latest_pct = pct_values[-1]
    ma10 = safe_mean(closes[-10:])
    ma20 = safe_mean(closes[-20:])
    ma60 = safe_mean(closes[-60:])
    ret5 = pct_change(closes[-1], closes[-6]) if len(closes) >= 6 else 0.0
    ret10 = pct_change(closes[-1], closes[-11]) if len(closes) >= 11 else 0.0
    ret20 = pct_change(closes[-1], closes[-21]) if len(closes) >= 21 else 0.0
    amount_5 = safe_mean(amounts[-5:])
    amount_prev_5 = safe_mean(amounts[-10:-5])
    turnover_5 = safe_mean(turnovers[-5:])
    volatility_10 = pd.Series(pct_values[-10:]).std(ddof=0) if len(pct_values) >= 10 else 0.0
    amount_ratio_5 = amount_5 / amount_prev_5 if amount_prev_5 > 0 else 1.0
    breakout_gap = pct_change(latest_close, max(highs[-20:-1])) if len(highs) >= 20 else 0.0
    prev_closes = [closes[0]] + closes[:-1]
    true_ranges = [
        max(high - low, abs(high - prev_close), abs(low - prev_close))
        for high, low, prev_close in zip(highs, lows, prev_closes)
    ]
    atr14 = safe_mean(true_ranges[-14:]) if len(true_ranges) >= 14 else safe_mean(true_ranges[-10:])
    support_10 = min(lows[-10:]) if len(lows) >= 10 else min(lows)
    resistance_20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)

    trend_score = 30.0
    if latest_close > ma20:
        trend_score += 18
    if ma10 > ma20:
        trend_score += 10
    if ma20 > ma60:
        trend_score += 12
    trend_score += clip(ret20 * 220, -10, 18)
    trend_score += clip(ret10 * 180, -8, 12)
    trend_score += clip(ret5 * 150, -6, 10)
    trend_score += clip(breakout_gap * 160, -6, 10)

    liquidity_score = 25.0
    liquidity_score += clip((amount_ratio_5 - 1.0) * 25, -8, 18)
    liquidity_score += clip(turnover_5 * 3, 0, 20)
    liquidity_score += clip((amount_5 / 100_000_000) * 1.2, 0, 25)

    risk_penalty = 0.0
    if latest_pct <= -9:
        risk_penalty += 18
    if latest_pct >= 9.5:
        risk_penalty += 8
    if volatility_10 >= 6:
        risk_penalty += 10

    technical_score = clip(0.62 * trend_score + 0.38 * liquidity_score - risk_penalty, 0, 100)

    return {
        "latest_close": latest_close,
        "latest_pct": latest_pct,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "ret5": ret5,
        "ret10": ret10,
        "ret20": ret20,
        "amount_5": amount_5,
        "amount_ratio_5": amount_ratio_5,
        "turnover_5": turnover_5,
        "volatility_10": float(volatility_10) if pd.notna(volatility_10) else 0.0,
        "breakout_gap": breakout_gap,
        "atr14": atr14,
        "support_10": support_10,
        "resistance_20": resistance_20,
        "technical_score": technical_score,
    }


def compute_sentiment_score(
    feature_map: dict[str, float],
    spot_turnover: float,
    spot_amount: float,
    spot_pct: float,
    spot_volume_ratio: float,
) -> float:
    score = 38.0
    score += clip(spot_pct * 3.4, -12, 26)
    score += clip(spot_turnover * 2.4, 0, 18)
    score += clip((spot_amount / 100_000_000) * 0.75, 0, 18)
    score += clip((spot_volume_ratio - 1.0) * 12, -8, 14)
    score += clip(feature_map["amount_ratio_5"] * 8 - 8, -6, 10)
    score += clip(feature_map["ret5"] * 120, -8, 10)
    if 4.5 <= spot_pct <= 10.5:
        score += 8
    if feature_map["volatility_10"] >= 6.5:
        score -= 8
    return clip(score, 0, 100)


def extract_event_articles(symbol: str, stock_name: str, news_df: pd.DataFrame) -> tuple[float, list[dict[str, Any]]]:
    if news_df is None or news_df.empty:
        return 50.0, []

    now = datetime.now(timezone.utc)
    articles: list[dict[str, Any]] = []
    aggregate_score = 0.0
    aliases = build_stock_aliases(stock_name=stock_name, symbol=symbol)

    for _, row in news_df.iterrows():
        title = str(row["新闻标题"])
        content = str(row["新闻内容"])
        source = str(row["文章来源"])
        source_category = str(row.get("来源类别", "个股资讯"))
        link = str(row.get("新闻链接", ""))
        published_at = row["发布时间"]
        if pd.isna(published_at):
            continue
        if not is_relevant_stock_event(stock_name=stock_name, symbol=symbol, row=row):
            continue

        text = f"{title} {content}"
        normalized_title = normalize_stock_name(title)
        normalized_content = normalize_stock_name(content)
        title_match = any(alias in title or alias in normalized_title for alias in aliases)
        content_match = any(alias in content or alias in normalized_content for alias in aliases)
        raw_score = 0.0
        event_type = classify_event_type_with_source(text=text, source_category=source_category)

        if any(keyword in text for keyword in LOW_SIGNAL_KEYWORDS):
            raw_score += 1.0
        else:
            for keyword, value in POSITIVE_KEYWORDS.items():
                if keyword in text:
                    raw_score += value
            for keyword, value in NEGATIVE_KEYWORDS.items():
                if keyword in text:
                    raw_score += value

        if source_category == "官方公告":
            raw_score += 6
            if any(keyword in text for keyword in ANNOUNCEMENT_NOISE_KEYWORDS):
                raw_score -= 4
        elif source_category == "券商研报":
            raw_score += 4

        if title_match:
            raw_score += 4
        elif content_match:
            raw_score += 1

        if source_category == "个股资讯" and not title_match:
            raw_score -= 2

        raw_score += SOURCE_BONUS.get(source, 0)

        age_hours = max(
            (now - published_at.to_pydatetime().replace(tzinfo=timezone.utc)).total_seconds() / 3600,
            0,
        )
        if age_hours <= 24:
            decay = 1.0
        elif age_hours <= 72:
            decay = 0.75
        else:
            decay = 0.5
        score = raw_score * decay

        if score >= 8:
            sentiment = "positive"
        elif score <= -8:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        impact_level = "high" if abs(score) >= 14 else "medium" if abs(score) >= 6 else "low"
        aggregate_score += score

        articles.append(
            {
                "event_id": hashlib.md5(
                    f"{stock_name}-{title}-{published_at}".encode("utf-8")
                ).hexdigest()[:12],
                "title": title,
                "publish_time": published_at.isoformat(),
                "source": source,
                "source_category": source_category,
                "event_type": event_type,
                "sentiment": sentiment,
                "impact_level": impact_level,
                "summary": content[:160] + ("..." if len(content) > 160 else ""),
                "link": link,
                "_score": round(score, 2),
            }
        )

    articles.sort(key=lambda item: item["_score"], reverse=True)
    selected = articles[:3]
    for item in selected:
        item.pop("_score", None)

    event_score = clip(50 + aggregate_score / max(len(articles), 1), 0, 100)
    return event_score, selected


def build_market_regime(top_sectors: list[dict[str, Any]], market_news: list[dict[str, Any]]) -> dict[str, Any]:
    if not top_sectors:
        return {
            "regime": "neutral",
            "confidence": 0.5,
            "suggested_exposure": 0.45,
            "breadth_score": 50.0,
            "northbound_score": 50.0,
            "momentum_score": 50.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    breadth_score = clip(safe_mean([sector["breadth_ratio"] * 100 for sector in top_sectors]), 0, 100)
    momentum_score = clip(safe_mean([sector["momentum_score"] for sector in top_sectors]), 0, 100)
    news_bias = 0.0
    for item in market_news[:5]:
        text = f"{item['title']} {item['summary']}"
        news_bias += sum(1 for keyword in ["上涨", "回暖", "突破", "回流", "强势"] if keyword in text)
        news_bias -= sum(1 for keyword in ["回落", "风险", "施压", "下跌", "翻绿"] if keyword in text)

    confidence = clip(
        (breadth_score * 0.4 + momentum_score * 0.5 + (50 + news_bias * 4) * 0.1) / 100,
        0,
        1,
    )

    if confidence >= 0.66:
        regime = "risk_on"
        exposure = 0.72
    elif confidence <= 0.4:
        regime = "risk_off"
        exposure = 0.25
    else:
        regime = "neutral"
        exposure = 0.48

    return {
        "regime": regime,
        "confidence": round(confidence, 4),
        "suggested_exposure": exposure,
        "breadth_score": round(breadth_score, 2),
        "northbound_score": round(50 + news_bias * 3, 2),
        "momentum_score": round(momentum_score, 2),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_mode_score(mode_id: str, record: dict[str, Any]) -> float:
    mode = MODE_INDEX[mode_id]
    components = {
        "industry": record["industry_score"],
        "technical": record["technical_score"],
        "event": record["event_score"],
        "sentiment": record["sentiment_score"],
    }
    score = sum(mode.score_weights[key] * components[key] for key in mode.score_weights)
    feature_map = record["feature_map"]
    top_event = record["events"][0] if record["events"] else None

    if mode_id == "balanced" and min(components.values()) >= 55:
        score += 5
    elif mode_id == "sector_rotation":
        if record["industry_rank"] <= 2:
            score += 8
        if record["industry_score"] >= 78:
            score += 5
    elif mode_id == "event_driven":
        if record["event_score"] >= 66:
            score += 8
        if top_event and top_event["sentiment"] == "positive":
            score += 5
        if any(event["sentiment"] == "negative" and event["impact_level"] == "high" for event in record["events"]):
            score -= 14
    elif mode_id == "trend_breakout":
        if feature_map["ma10"] > feature_map["ma20"] > feature_map["ma60"]:
            score += 8
        if feature_map["breakout_gap"] >= -0.01:
            score += 5
        if record["spot_pct"] < -2:
            score -= 8
    elif mode_id == "short_term_relay":
        if record["spot_pct"] >= 6:
            score += 10
        if record["spot_turnover"] >= 4:
            score += 6
        if record["spot_volume_ratio"] >= 1.8:
            score += 5
        if feature_map["latest_pct"] < 0:
            score -= 10

    return round(clip(score, 0, 100), 2)


def record_matches_mode(mode_id: str, record: dict[str, Any]) -> bool:
    feature_map = record["feature_map"]
    if mode_id == "balanced":
        return record["industry_score"] >= 52 and record["technical_score"] >= 50
    if mode_id == "sector_rotation":
        return record["industry_rank"] <= 3 and record["industry_score"] >= 60
    if mode_id == "event_driven":
        return record["event_score"] >= 53 or len(record["events"]) >= 1
    if mode_id == "trend_breakout":
        return (
            record["technical_score"] >= 58
            and feature_map["ma10"] >= feature_map["ma20"]
            and feature_map["ret10"] >= -0.02
        )
    if mode_id == "short_term_relay":
        return (
            record["sentiment_score"] >= 58
            and record["spot_pct"] >= 2
            and max(record["spot_turnover"], feature_map["turnover_5"]) >= 2
        )
    return True


def build_reasons_for_mode(
    mode_id: str, record: dict[str, Any], sector_names: list[str]
) -> list[dict[str, str]]:
    feature_map = record["feature_map"]
    top_event = record["events"][0]["title"] if record["events"] else ""

    if mode_id == "sector_rotation":
        return [
            {
                "label": "行业强度",
                "detail": f"{record['industry']} 位于当前强势行业前列，属于 {', '.join(sector_names[:3])} 主线之一。",
            },
            {
                "label": "扩散确认",
                "detail": (
                    f"板块分 {record['industry_score']:.1f}，个股当日涨幅 {record['spot_pct']:.1f}%，"
                    "具备主线扩散跟涨条件。"
                ),
            },
            {
                "label": "交易关注",
                "detail": "优先观察主线延续和板块内二次发酵，而不是脱离板块单独追涨。",
            },
        ]

    if mode_id == "event_driven":
        return [
            {
                "label": "事件催化",
                "detail": top_event or "近三日出现有效新闻催化，进入消息面优先跟踪池。",
            },
            {
                "label": "情绪确认",
                "detail": (
                    f"事件分 {record['event_score']:.1f}，情绪分 {record['sentiment_score']:.1f}，"
                    "说明新闻并非纯静态公告。"
                ),
            },
            {
                "label": "执行方式",
                "detail": "更适合盘前筛选或消息落地后的次日跟踪，强调催化是否持续。",
            },
        ]

    if mode_id == "trend_breakout":
        return [
            {
                "label": "均线结构",
                "detail": (
                    f"MA10 {feature_map['ma10']:.2f} / MA20 {feature_map['ma20']:.2f} / "
                    f"MA60 {feature_map['ma60']:.2f}，趋势结构保持偏强。"
                ),
            },
            {
                "label": "放量突破",
                "detail": (
                    f"近 5 日成交额倍率 {feature_map['amount_ratio_5']:.2f}，"
                    f"20 日收益 {feature_map['ret20'] * 100:.1f}%。"
                ),
            },
            {
                "label": "持有节奏",
                "detail": "更适合按照趋势节奏持有，等待均线和量能共同失效再撤退。",
            },
        ]

    if mode_id == "short_term_relay":
        return [
            {
                "label": "情绪强度",
                "detail": (
                    f"当日涨幅 {record['spot_pct']:.1f}%，换手 {record['spot_turnover']:.1f}%，"
                    f"量比 {record['spot_volume_ratio']:.2f}。"
                ),
            },
            {
                "label": "接力质量",
                "detail": (
                    f"情绪分 {record['sentiment_score']:.1f}，"
                    f"近 5 日量能提升 {feature_map['amount_ratio_5']:.2f} 倍。"
                ),
            },
            {
                "label": "执行方式",
                "detail": "适合做强势股次日跟踪，不适合把它当作中线持仓池。",
            },
        ]

    return [
        {
            "label": "行业轮动",
            "detail": f"{record['industry']} 当前仍在强势行业监控池内，优先级高于普通板块。",
        },
        {
            "label": "技术结构",
            "detail": (
                f"{record['name']} 近 20 日收益 {feature_map['ret20'] * 100:.1f}%，"
                f"技术分 {record['technical_score']:.1f}。"
            ),
        },
        {
            "label": "事件辅助",
            "detail": top_event or "近期无显著负面事件，默认由行业与技术面驱动。",
        },
    ]


def build_risk_plan(mode_id: str, record: dict[str, Any], market_regime: str) -> dict[str, Any]:
    feature_map = record["feature_map"]
    reference_price = record["spot_price"] if record["spot_price"] > 0 else feature_map["latest_close"]
    atr_value = max(feature_map.get("atr14", 0.0), reference_price * 0.015)
    support_price = max(feature_map.get("support_10", 0.0), 0.0)
    resistance_price = max(feature_map.get("resistance_20", 0.0), reference_price)
    stop_bounds = {
        "balanced": (0.04, 0.078, 1.55, 1.8, 3.0),
        "sector_rotation": (0.045, 0.082, 1.65, 1.9, 3.1),
        "event_driven": (0.038, 0.072, 1.4, 1.7, 2.8),
        "trend_breakout": (0.045, 0.09, 1.8, 2.0, 3.3),
        "short_term_relay": (0.032, 0.065, 1.25, 1.6, 2.5),
    }
    min_stop_pct, max_stop_pct, atr_mult, tp1_mult, tp2_mult = stop_bounds[mode_id]
    raw_stop_candidates = [
        reference_price - atr_value * atr_mult,
        feature_map["ma20"] * 0.988,
        support_price * 0.994 if support_price else 0.0,
    ]
    raw_stop_price = max(candidate for candidate in raw_stop_candidates if candidate > 0)
    stop_pct = clip((reference_price - raw_stop_price) / max(reference_price, 0.01), min_stop_pct, max_stop_pct)
    stop_loss_price = round(reference_price * (1 - stop_pct), 2)
    risk_unit = max(reference_price - stop_loss_price, reference_price * min_stop_pct)

    take_profit_price_1 = round(
        max(reference_price + risk_unit * tp1_mult, resistance_price * 1.01 if resistance_price else 0.0),
        2,
    )
    take_profit_price_2 = round(reference_price + risk_unit * tp2_mult, 2)
    take_profit_pct_1 = (take_profit_price_1 - reference_price) / max(reference_price, 0.01)
    take_profit_pct_2 = (take_profit_price_2 - reference_price) / max(reference_price, 0.01)
    trailing_stop_price = round(max(feature_map["ma10"] * 0.992, reference_price - atr_value * 1.15), 2)

    mode_position_cap = {
        "balanced": 0.12,
        "sector_rotation": 0.14,
        "event_driven": 0.1,
        "trend_breakout": 0.13,
        "short_term_relay": 0.09,
    }[mode_id]
    regime_factor = {"risk_on": 1.0, "neutral": 0.82, "risk_off": 0.58}.get(market_regime, 0.8)
    volatility_factor = 0.72 if feature_map["volatility_10"] >= 6 else 0.85 if feature_map["volatility_10"] >= 4.5 else 1.0
    chase_factor = 0.72 if record["spot_pct"] >= 8 else 0.84 if record["spot_pct"] >= 5 else 1.0
    position_max = clip(mode_position_cap * regime_factor * volatility_factor * chase_factor, 0.04, 0.18)
    position_min = clip(position_max * 0.6, 0.02, position_max)
    max_portfolio_risk = position_max * stop_pct
    risk_reward_ratio = max((take_profit_price_1 - reference_price) / max(reference_price - stop_loss_price, 0.01), 0.5)

    if record["spot_pct"] >= 8:
        action_bias = "谨慎追高"
        action_note = "当前价格已经偏离均线较多，若参与建议只做试仓，不适合一次性重仓。"
    elif reference_price > feature_map["ma10"] * 1.03:
        action_bias = "分批试仓"
        action_note = "价格强于短均线，但位置并不低，适合等待回踩或用更小仓位跟踪。"
    elif reference_price >= feature_map["ma20"]:
        action_bias = "跟踪持有"
        action_note = "当前价格仍处在趋势保护带上方，更适合按纪律跟踪，而不是频繁换股。"
    else:
        action_bias = "等待确认"
        action_note = "当前位置贴近趋势支撑，宜等待企稳或放量再提高仓位。"

    price_basis = "当前最新价" if record["spot_price"] > 0 else "最近收盘价"
    execution_notes = [
        f"止损线参考 {stop_loss_price:.2f} 元，跌破后优先缩回观察仓，若次日无法收回则考虑离场。",
        f"第一止盈位参考 {take_profit_price_1:.2f} 元，可考虑先兑现部分利润。",
        f"第二止盈位参考 {take_profit_price_2:.2f} 元，若继续上行则把跟踪止损上移到 {trailing_stop_price:.2f} 元附近。",
        "更适合分批确认，不建议在信号刚触发时一次性追入。",
    ]

    return {
        "price_basis": price_basis,
        "reference_price": round(reference_price, 2),
        "stop_loss_price": stop_loss_price,
        "stop_loss_pct": round(stop_pct, 4),
        "take_profit_price_1": take_profit_price_1,
        "take_profit_pct_1": round(take_profit_pct_1, 4),
        "take_profit_price_2": take_profit_price_2,
        "take_profit_pct_2": round(take_profit_pct_2, 4),
        "trailing_stop_price": trailing_stop_price,
        "suggested_position_min": round(position_min, 4),
        "suggested_position_max": round(position_max, 4),
        "max_portfolio_risk": round(max_portfolio_risk, 4),
        "risk_reward_ratio": round(risk_reward_ratio, 2),
        "action_bias": action_bias,
        "action_note": action_note,
        "analysis_method": "rule_based_v1",
        "execution_notes": execution_notes,
    }


def build_ai_risk_analysis(mode_id: str, record: dict[str, Any], risk_plan: dict[str, Any]) -> dict[str, Any]:
    mode = MODE_INDEX[mode_id]
    event_text = record["events"][0]["title"] if record["events"] else "当前没有高置信度事件催化，风控更依赖技术位和波动率。"
    confidence = 0.72
    if risk_plan["risk_reward_ratio"] >= 2.0:
        confidence += 0.06
    if record["feature_map"]["volatility_10"] >= 6:
        confidence -= 0.08
    if record["spot_pct"] >= 8:
        confidence -= 0.06
    confidence = clip(confidence, 0.45, 0.9)

    summary = (
        f"基于 {mode.display_name} 模式，当前更适合 {risk_plan['action_bias']}。"
        f"规则建议以 {risk_plan['stop_loss_price']:.2f} 元作为防守位，"
        f"并在 {risk_plan['take_profit_price_1']:.2f} / {risk_plan['take_profit_price_2']:.2f} 元分批兑现。"
    )
    highlights = [
        (
            f"当前模式更看重 {', '.join(mode.preferred_features)}，"
            "因此执行上更适合轻仓试错、确认后再逐步加码。"
        ),
        (
            f"近 10 日波动率为 {record['feature_map']['volatility_10']:.2f}，"
            "因此更适合分批执行，不建议脱离纪律临时放大暴露。"
        ),
        f"最近的重要事件提要：{event_text}",
    ]

    return {
        "status": "rule_stub_ready",
        "model": None,
        "confidence": round(confidence, 2),
        "summary": summary,
        "highlights": highlights,
        "next_step": "后续接入 AI 后，可在这一区域输出个性化止盈止损解释和执行节奏建议。",
        "source": "rules",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_risk_controls(mode_id: str, record: dict[str, Any]) -> list[str]:
    feature_map = record["feature_map"]
    controls = [
        "单票宜轻仓起步，不建议在信号刚触发时一次性重仓。",
        "若收盘跌破 20 日线且成交额放大，优先主动减仓。",
    ]

    if mode_id == "event_driven":
        controls.append("若 48 小时内没有新增催化，优先从消息面模式里移除。")
    elif mode_id == "trend_breakout":
        controls.append("趋势模式更关注 10 日线和 20 日线，不建议频繁追涨杀跌。")
    elif mode_id == "short_term_relay":
        controls.append("若次日高开后无法延续强势，优先按纪律快速减仓。")
    elif mode_id == "sector_rotation":
        controls.append("若所属行业跌出强势行业前五，优先降低该模式暴露。")

    if record["spot_pct"] >= 9.5:
        controls.append("当日已接近涨停，避免尾盘情绪化追高。")
    if feature_map["volatility_10"] >= 5.5:
        controls.append("近 10 日波动偏大，更适合降低暴露而非加杠杆。")
    return controls


def build_feature_scores(
    mode_id: str, record: dict[str, Any]
) -> list[dict[str, Any]]:
    feature_map = record["feature_map"]
    items = [
        {
            "name": "行业强度",
            "value": round(record["industry_score"], 2),
            "description": (
                f"{record['industry']} 当前位于强势行业监控池，行业排序第 {record['industry_rank']} 位。"
                f" 该维度反映主线持续性、板块扩散能力和资金共识。"
            ),
        },
        {
            "name": "技术结构",
            "value": round(record["technical_score"], 2),
            "description": (
                f"20 日收益 {feature_map['ret20'] * 100:.1f}%，"
                f"量能倍率 {feature_map['amount_ratio_5']:.2f}，MA10 / MA20 / MA60 为 "
                f"{feature_map['ma10']:.2f} / {feature_map['ma20']:.2f} / {feature_map['ma60']:.2f}。"
            ),
        },
        {
            "name": "事件强度",
            "value": round(record["event_score"], 2),
            "description": (
                "基于官方公告、个股资讯和券商研报的来源质量、时效性与关键词权重综合计算。"
                " 得分越高，说明近期催化越明确。"
            ),
        },
        {
            "name": "情绪热度",
            "value": round(record["sentiment_score"], 2),
            "description": (
                f"日内涨幅 {record['spot_pct']:.1f}%，"
                f"换手 {record['spot_turnover']:.1f}%，量比 {record['spot_volume_ratio']:.2f}。"
                f" 该维度主要衡量资金活跃度、接力意愿和短线拥挤程度。"
            ),
        },
    ]

    emphasis = {
        "event_driven": "事件强度",
        "trend_breakout": "技术结构",
        "short_term_relay": "情绪热度",
        "sector_rotation": "行业强度",
        "balanced": "行业强度",
    }[mode_id]

    for item in items:
        if item["name"] == emphasis:
            item["description"] = f"当前模式重点关注该维度。{item['description']}"
            break
    return items


def build_stock_detail(
    mode_id: str,
    record: dict[str, Any],
    sector_names: list[str],
    market_regime: str,
) -> dict[str, Any]:
    mode = MODE_INDEX[mode_id]
    risk_plan = build_risk_plan(mode_id, record, market_regime)
    ai_risk_analysis = build_ai_risk_analysis(mode_id, record, risk_plan)
    thesis_templates = {
        "balanced": (
            f"{record['name']} 同时满足行业、技术、消息和情绪四个维度的均衡要求，"
            f"当前模式分 {record['mode_scores'][mode_id]:.1f}，适合作为默认候选股跟踪。"
        ),
        "sector_rotation": (
            f"{record['name']} 属于 {record['industry']} 强势主线中的代表标的，"
            "更适合作为行业扩散阶段的跟踪对象。"
        ),
        "event_driven": (
            f"{record['name']} 的新闻事件打分为 {record['event_score']:.1f}，"
            "适合做盘前消息驱动的重点观察。"
        ),
        "trend_breakout": (
            f"{record['name']} 具备较完整的均线多头与放量突破结构，"
            f"技术分 {record['technical_score']:.1f}，适合趋势跟踪。"
        ),
        "short_term_relay": (
            f"{record['name']} 当前日内热度高、换手活跃，情绪分 {record['sentiment_score']:.1f}，"
            "适合短线接力风格的次日观察。"
        ),
    }
    market_context = (
        f"当前市场重点围绕 {', '.join(sector_names[:5])} 展开。"
        f"当前查看的是“{mode.display_name}”模式，它更强调 {', '.join(mode.preferred_features)}。"
    )

    return {
        "symbol": record["symbol"],
        "name": record["name"],
        "industry": record["industry"],
        "thesis": thesis_templates[mode_id],
        "market_context": market_context,
        "feature_scores": build_feature_scores(mode_id, record),
        "recent_events": record["events"],
        "risk_plan": risk_plan,
        "ai_risk_analysis": ai_risk_analysis,
        "risk_controls": risk_plan["execution_notes"] + build_risk_controls(mode_id, record),
    }


def select_news_watchlist(records: list[dict[str, Any]], max_size: int) -> list[dict[str, Any]]:
    watchlist: dict[str, dict[str, Any]] = {}
    ranking_groups = [
        sorted(records, key=lambda item: item["baseline_score"], reverse=True)[:max_size],
        sorted(records, key=lambda item: item["technical_score"], reverse=True)[:max_size],
        sorted(records, key=lambda item: item["sentiment_score"], reverse=True)[:max_size],
    ]
    for group in ranking_groups:
        for record in group:
            watchlist.setdefault(record["symbol"], record)
    return list(watchlist.values())


def build_mode_payload(
    mode_id: str,
    records: list[dict[str, Any]],
    sector_names: list[str],
    market_regime: str,
    config: SelectionConfig,
) -> dict[str, Any]:
    mode = MODE_INDEX[mode_id]
    eligible = [record for record in records if record_matches_mode(mode_id, record)]
    if len(eligible) < config.final_candidate_count:
        eligible = records[:]

    ranked = sorted(
        eligible,
        key=lambda item: (item["mode_scores"][mode_id], item["baseline_score"]),
        reverse=True,
    )[: config.final_candidate_count]

    items: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    for index, record in enumerate(ranked, start=1):
        top_event_title = record["events"][0]["title"] if record["events"] else ""
        items.append(
            {
                "symbol": record["symbol"],
                "name": record["name"],
                "industry": record["industry"],
                "rank": index,
                "base_score": round(record["baseline_score"], 2),
                "event_score": round(record["event_score"], 2),
                "risk_adjusted_score": round(record["mode_scores"][mode_id], 2),
                "holding_window": mode.holding_window,
                "reasons": build_reasons_for_mode(mode_id, record, sector_names),
                "event_tags": [event["event_type"] for event in record["events"][:3]] if top_event_title else [],
            }
        )
        details[record["symbol"]] = build_stock_detail(mode_id, record, sector_names, market_regime)

    return {
        "mode_id": mode.mode_id,
        "display_name": mode.display_name,
        "description": mode.description,
        "holding_window": mode.holding_window,
        "items": items,
        "stock_details": details,
        "selection_meta": {
            "candidate_count": len(items),
            "preferred_features": mode.preferred_features,
        },
    }


def generate_daily_candidates(config: Optional[SelectionConfig] = None) -> dict[str, Any]:
    selection_config = config or SelectionConfig()
    adapter = AKShareMarketDataAdapter()
    code_name_df = adapter.fetch_code_name_map()
    code_lookup = {
        normalize_stock_name(str(row["name"])): str(row["code"]).zfill(6)
        for _, row in code_name_df.iterrows()
    }

    industries_df = score_industries(adapter.fetch_industry_rankings())
    top_industries_df = industries_df.head(selection_config.top_industry_count)

    top_sectors: list[dict[str, Any]] = []
    record_map: dict[str, dict[str, Any]] = {}
    scan_summary: list[dict[str, Any]] = []

    for sector_rank, (_, sector) in enumerate(top_industries_df.iterrows(), start=1):
        sector_name = str(sector["板块名称"])
        sector_code = str(sector.get("板块代码", ""))
        top_sectors.append(
            {
                "sector_code": sector_code,
                "sector_name": sector_name,
                "strength_score": round(float(sector["strength_score"]), 2),
                "momentum_score": round(float(sector["momentum_score"]), 2),
                "capital_consensus_score": round(float(sector["capital_consensus_score"]), 2),
                "heat_score": round(float(sector["heat_score"]), 2),
                "breadth_ratio": round(float(sector["breadth_ratio"]), 4),
            }
        )

        constituents_df = adapter.fetch_industry_constituents(
            sector_name, limit=selection_config.stocks_per_industry
        )
        if constituents_df.empty:
            leader_name = str(sector.get("领涨股票", "")).strip()
            leader_code = code_lookup.get(normalize_stock_name(leader_name))
            if leader_name and leader_code:
                constituents_df = pd.DataFrame(
                    [
                        {
                            "序号": 1,
                            "代码": leader_code,
                            "名称": leader_name,
                            "最新价": 0.0,
                            "涨跌幅": float(sector.get("领涨股票-涨跌幅", 0.0)),
                            "涨跌额": 0.0,
                            "成交量": 0.0,
                            "成交额": 0.0,
                            "振幅": 0.0,
                            "最高": 0.0,
                            "最低": 0.0,
                            "今开": 0.0,
                            "昨收": 0.0,
                            "换手率": float(sector.get("换手率", 0.0)),
                            "量比": 1.0,
                            "流通股": 0.0,
                            "流通市值": 0.0,
                            "市盈率-动态": 0.0,
                            "市净率": 0.0,
                            "data_source": "industry_leader_fallback",
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ]
                )

        scan_summary.append(
            {
                "sector_name": sector_name,
                "sector_code": sector_code,
                "scanned_count": int(len(constituents_df)),
                "data_source": (
                    str(constituents_df.iloc[0].get("data_source", "unknown"))
                    if not constituents_df.empty
                    else "empty"
                ),
            }
        )

        for _, row in constituents_df.iterrows():
            symbol = str(row["代码"]).zfill(6)
            stock_name = str(row["名称"]).strip()
            if not symbol or not stock_name or "ST" in stock_name.upper():
                continue

            spot_turnover = float(pd.to_numeric(row.get("换手率", 0.0), errors="coerce") or 0.0)
            spot_amount = float(pd.to_numeric(row.get("成交额", 0.0), errors="coerce") or 0.0)

            hist_df = adapter.fetch_stock_daily_history(symbol)
            feature_map = compute_stock_features(hist_df)
            if feature_map is None or len(hist_df) < selection_config.min_history_days:
                continue

            effective_turnover = max(spot_turnover, float(feature_map["turnover_5"]))
            effective_amount = max(spot_amount, float(feature_map["amount_5"]))
            if effective_turnover < selection_config.min_turnover_rate:
                continue
            if effective_amount < selection_config.min_amount:
                continue

            spot_pct = float(pd.to_numeric(row.get("涨跌幅", feature_map["latest_pct"]), errors="coerce") or 0.0)
            spot_volume_ratio = float(pd.to_numeric(row.get("量比", 1.0), errors="coerce") or 1.0)
            spot_price = float(pd.to_numeric(row.get("最新价", feature_map["latest_close"]), errors="coerce") or feature_map["latest_close"])
            industry_score = round(float(sector["sector_score"]), 2)
            technical_score = round(float(feature_map["technical_score"]), 2)
            sentiment_score = round(
                compute_sentiment_score(
                    feature_map=feature_map,
                    spot_turnover=spot_turnover,
                    spot_amount=spot_amount,
                    spot_pct=spot_pct,
                    spot_volume_ratio=spot_volume_ratio,
                ),
                2,
            )
            baseline_score = round(
                0.34 * industry_score + 0.38 * technical_score + 0.28 * sentiment_score,
                2,
            )

            new_record = {
                "symbol": symbol,
                "name": stock_name,
                "industry": sector_name,
                "industry_code": sector_code,
                "industry_rank": sector_rank,
                "industry_score": industry_score,
                "spot_turnover": spot_turnover,
                "spot_amount": spot_amount,
                "spot_pct": spot_pct,
                "spot_price": spot_price,
                "spot_volume_ratio": spot_volume_ratio,
                "feature_map": feature_map,
                "technical_score": technical_score,
                "sentiment_score": sentiment_score,
                "baseline_score": baseline_score,
                "constituent_source": str(row.get("data_source", "unknown")),
                "event_score": 50.0,
                "events": [],
                "mode_scores": {},
            }

            existing = record_map.get(symbol)
            if existing is None or new_record["industry_score"] > existing["industry_score"]:
                record_map[symbol] = new_record

    universe_records = list(record_map.values())
    universe_records.sort(key=lambda item: item["baseline_score"], reverse=True)
    preliminary = universe_records[: selection_config.preliminary_candidate_count]

    news_watchlist = select_news_watchlist(preliminary, max_size=selection_config.final_candidate_count * 2)
    for record in news_watchlist:
        news_df = adapter.fetch_stock_event_feed(symbol=record["symbol"], stock_name=record["name"])
        event_score, events = extract_event_articles(
            symbol=record["symbol"],
            stock_name=record["name"],
            news_df=news_df,
        )
        record["event_score"] = round(event_score, 2)
        record["events"] = events

    for record in universe_records:
        if not record["mode_scores"]:
            record["mode_scores"] = {}
        for mode in STRATEGY_MODES:
            record["mode_scores"][mode.mode_id] = build_mode_score(mode.mode_id, record)

    market_news_df = adapter.fetch_market_news(limit=8)
    market_news = [
        {
            "title": str(row["标题"]),
            "summary": str(row["摘要"]),
            "publish_time": row["发布时间"].isoformat(),
            "link": str(row["链接"]),
        }
        for _, row in market_news_df.iterrows()
    ]

    market_regime = build_market_regime(top_sectors=top_sectors, market_news=market_news)
    sector_names = [sector["sector_name"] for sector in top_sectors]

    strategy_modes = {
        mode.mode_id: build_mode_payload(
        mode_id=mode.mode_id,
        records=universe_records,
        sector_names=sector_names,
        market_regime=market_regime["regime"],
        config=selection_config,
    )
        for mode in STRATEGY_MODES
    }
    mode_summaries = [
        {
            "mode_id": mode.mode_id,
            "display_name": mode.display_name,
            "description": mode.description,
            "holding_window": mode.holding_window,
        }
        for mode in STRATEGY_MODES
    ]

    default_mode_payload = strategy_modes[DEFAULT_MODE_ID]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trade_date": datetime.now().date().isoformat(),
        "strategy_version": "v2-akshare-multi-mode",
        "default_mode": DEFAULT_MODE_ID,
        "mode_summaries": mode_summaries,
        "market_regime": market_regime,
        "top_sectors": top_sectors,
        "market_news": market_news,
        "strategy_modes": strategy_modes,
        "candidate_pool": default_mode_payload["items"],
        "stock_details": default_mode_payload["stock_details"],
        "selection_meta": {
            "industry_source": str(industries_df.iloc[0].get("data_source", "unknown"))
            if not industries_df.empty
            else "unknown",
            "constituent_scan_mode": f"行业前 {selection_config.stocks_per_industry} 成分股全扫",
            "total_universe_size": len(universe_records),
            "news_watchlist_size": len(news_watchlist),
            "scan_summary": scan_summary,
        },
    }
