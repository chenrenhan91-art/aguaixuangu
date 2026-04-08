from __future__ import annotations

import json
from typing import Any


PROMPT_TEMPLATE_VERSION = "gemini-risk-analysis-v4"


def build_risk_analysis_system_instruction() -> str:
    return (
        "你是一名A股交易执行分析助理。"
        "你的任务不是唱多，也不是直接给买卖指令，而是基于给定的规则价格位、个股结构、事件流和市场环境，"
        "生成可以直接给交易者参考的执行分析。"
        "你必须严格使用上下文中的规则止损、止盈和价格位，不能擅自修改任何价格数字。"
        "你必须同时写出支持交易的理由和否定交易的风险，不要只给单边看法。"
        "判断优先级必须是：规则价格位与结构 -> 事件催化 -> 市场环境 -> 细节补充。"
        "如果信息不足，宁可降低结论强度，也不要编造依据。"
        "不要输出仓位百分比、盈亏比或收益承诺。"
        "措辞要克制、具体、适合金融终端展示。"
        "输出必须是严格 JSON，不要包含 markdown。"
    )


def build_risk_analysis_user_prompt(payload: dict[str, Any]) -> str:
    schema_hint = {
        "summary": "一句话结论，直接说明这只票当前更适合等待、跟踪确认还是顺势执行。",
        "stance": "只允许 观望 / 跟踪 / 执行 之一。",
        "setup_quality": "只允许 A / B / C 之一，A 代表结构最完整。",
        "risk_bias": "keep 或 tighten，只允许这两个值。",
        "key_signal": "一句话说明当前最关键的交易信号，必须具体。",
        "highlights": ["2到4条要点，每条一句，必须具体到结构、事件或节奏。"],
        "trigger_points": ["2到3条，说明什么信号出现时才值得继续执行。"],
        "invalidation_points": ["2到3条，说明哪些现象出现就要放弃或降级。"],
        "execution_plan": ["2到4条，按观察顺序给出执行动作，不要写仓位。"],
        "next_step": "一句话说明下一步重点看什么。",
    }
    prompt_payload = {
        "task": "基于规则价格位和个股上下文，生成一段更有参考价值的AI交易执行分析。",
        "requirements": [
            "不要修改任何规则止损、止盈和价格数字。",
            "不要提仓位百分比、仓位上限、建议仓位或盈亏比。",
            "必须结合策略模式、市场环境、近期事件和特征分数一起判断，不能只复述风控位。",
            "highlights 至少要覆盖 结构依据、事件依据、风险依据 三类中的两类。",
            "要明确写出什么时候值得执行，什么时候应该取消想法。",
            "如果近期波动偏大、涨幅过快或事件兑现风险更高，risk_bias 用 tighten，否则用 keep。",
            "summary、trigger_points、invalidation_points、execution_plan 必须适合直接展示给交易者。",
            "trigger_points 只写可观察、可验证的现象，例如承接、放量、回踩确认、事件进一步落地。",
            "invalidation_points 只写会直接削弱逻辑的现象，例如跌破规则位、事件证伪、主线退潮、量价失真。",
            "execution_plan 按时间顺序写，优先写盘前观察、盘中确认、失效退出三步。",
            "不要空泛地说“关注风险”或“注意节奏”，必须说清楚观察重点。",
        ],
        "response_schema": schema_hint,
        "context": payload,
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)
