from __future__ import annotations

import json
from typing import Any


MARKET_SENTIMENT_PROMPT_VERSION = "gemini-market-sentiment-v3"
SENTIMENT_LEXICON = [
    "冰点防守",
    "退潮试错",
    "弱修复",
    "轮动博弈",
    "主线强化",
]


def build_market_sentiment_system_instruction() -> str:
    return (
        "你是一名A股盘前策略助理。"
        "你需要根据市场广度、动量、北向、强势行业和市场新闻，"
        "给出一个精确、克制、适合金融终端展示的市场情绪判断。"
        "禁止使用空泛措辞，例如‘还不错’‘一般般’。"
        "判断优先级必须是：广度与动量 -> 主线集中度 -> 北向与新闻验证。"
        "如果信号冲突，优先降低情绪档位，不要为了乐观而拔高结论。"
        "sentiment_label 必须从给定词库中选择最贴近当前市场的一个。"
        "summary 必须简洁、有交易指向，不超过36个汉字。"
        "需要明确今天更值得做什么，不值得做什么。"
        "输出必须是严格 JSON，不要包含 markdown。"
    )


def build_market_sentiment_user_prompt(payload: dict[str, Any]) -> str:
    schema_hint = {
        "sentiment_label": f"必须从这些词中选择一个: {SENTIMENT_LEXICON}",
        "sentiment_score": "0到100之间的数字，越高代表情绪越强。",
        "summary": "一句精炼描述，直接说明当前市场情绪和盘前操作重心。",
        "action_bias": "只能是 顺势跟随 / 精选轮动 / 控仓观察 之一。",
        "preferred_setup": "一句话说明今天优先做哪类机会。",
        "avoid_action": "一句话说明今天最不该做的动作。",
        "dominant_signal": "一句话说明判断该情绪的主导信号。",
        "tags": ["3个以内的短标签，例如 主线集中、轮动偏快、追高降速。"],
        "watchouts": ["2条以内的风险提醒，每条一句。"],
    }
    prompt_payload = {
        "task": "根据盘前市场快照生成一段可直接展示在A股终端首页的AI市场情绪分析。",
        "requirements": [
            "不要复述原始数据，要把数据转成交易者能立刻理解的市场情绪判断。",
            "summary 需要体现当前更适合顺势跟随、精选轮动还是控仓观察。",
            "preferred_setup 必须具体到机会类型，例如主线分歧回流、事件确认前排、低位二次确认。",
            "avoid_action 必须具体到错误动作，例如追高后排、分散铺仓、逆势抄底。",
            "dominant_signal 必须指出驱动情绪判断的主导变量，例如广度、动量、北向或主线集中度。",
            "watchouts 只写最关键的两条，不要泛泛提示。",
            "tags 要像终端标签，尽量短，便于扫读。",
            "情绪档位只允许这五种：冰点防守、退潮试错、弱修复、轮动博弈、主线强化。",
            "如果广度和动量同时很强，且主线集中度高，优先考虑 主线强化。",
            "如果板块轮动较快、强弱切换明显，但市场尚未明显退潮，优先考虑 轮动博弈。",
            "如果广度偏弱且缺乏共振，优先考虑 退潮试错、弱修复 或 冰点防守。",
        ],
        "response_schema": schema_hint,
        "context": payload,
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)
