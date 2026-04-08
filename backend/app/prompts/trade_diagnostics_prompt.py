from __future__ import annotations

import json
from typing import Any


TRADE_DIAGNOSTICS_PROMPT_VERSION = "gemini-trade-diagnostics-v1"


def build_trade_diagnostics_system_instruction() -> str:
    return (
        "你是一名A股历史交易复盘分析助理。"
        "你的任务是基于结构化的历史交割单诊断结果，总结用户的交易风格、有效优势、主要漏洞和下一阶段优化动作。"
        "你不能编造不存在的收益、回撤、胜率或股票案例，只能使用给定上下文。"
        "优先级必须是：闭环交易统计 -> 盈亏对比 -> 错误模式/有效模式 -> 用户执行建议。"
        "输出要克制、具体，适合展示在交易终端的 AI 复盘窗口。"
        "不要给确定性承诺，不要写收益预测。"
        "输出必须是严格 JSON，不要包含 markdown。"
    )


def build_trade_diagnostics_user_prompt(payload: dict[str, Any]) -> str:
    schema_hint = {
        "summary": "一句话概括当前用户最值得保留的交易方式和最需要修正的问题。",
        "trader_profile": "一句话概括用户当前最接近的交易者画像。",
        "strengths": ["2到4条，说明当前有效的交易习惯或优势来源。"],
        "weaknesses": ["2到4条，说明当前最关键的执行漏洞或亏损来源。"],
        "behavior_tags": ["2到4个短标签，例如 顺势波段、追高回撤、补仓偏多。"],
        "adjustments": ["3到5条，必须是可执行的优化动作，不要空话。"],
        "next_cycle_plan": ["3条以内，按下一交易周期的执行顺序给计划。"],
    }
    prompt_payload = {
        "task": "基于历史交易诊断结果，生成一段可直接展示给用户的 AI 交易复盘分析。",
        "requirements": [
            "不要复述所有字段，只提炼最有决策价值的结论。",
            "strengths 和 weaknesses 需要同时出现，避免只说优点或只说问题。",
            "adjustments 必须是具体动作，例如收紧买点、减少补仓、只做主线确认等。",
            "next_cycle_plan 必须按先后顺序写，适合用户下一阶段直接执行。",
            "如果闭环交易数较少或数据可信度有限，要在 summary 中体现结论强度有限。",
            "不要写仓位百分比、收益承诺或模糊表述。",
        ],
        "response_schema": schema_hint,
        "context": payload,
    }
    return json.dumps(prompt_payload, ensure_ascii=False, indent=2)
