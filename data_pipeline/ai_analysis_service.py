"""
AI 交易执行分析服务 - 集成 Gemini/ChatGPT 进行个股风控分析
用于 make.com 工作流调用或直接后端使用
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests


def call_gemini_api(prompt: str, api_key: Optional[str] = None) -> str:
    """
    调用 Google Gemini API 生成 AI 分析
    支持 gemini-2.0-flash 或 gemini-1.5-pro

    Args:
        prompt: 分析提示文本
        api_key: Gemini API Key (默认从环境变量读取)

    Returns:
        AI 生成的分析文本
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.9,
            "maxOutputTokens": 1024,
        },
    }

    try:
        resp = requests.post(
            f"{url}?key={api_key}",
            json=payload,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        if (
            result.get("candidates")
            and len(result["candidates"]) > 0
            and result["candidates"][0].get("content", {}).get("parts")
        ):
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return "AI 返回为空"
    except requests.exceptions.RequestException as e:
        return f"API 调用失败: {str(e)}"


def call_chatgpt_api(prompt: str, api_key: Optional[str] = None) -> str:
    """
    调用 OpenAI ChatGPT API 生成分析
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in environment")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("choices") and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        return "AI 返回为空"
    except requests.exceptions.RequestException as e:
        return f"API 调用失败: {str(e)}"


def build_analysis_prompt(
    stock_name: str,
    stock_symbol: str,
    risk_plan: dict[str, Any],
    record: dict[str, Any],
    mode_name: str,
) -> str:
    """
    为单只股票构建 AI 分析提示词
    """
    event_text = record.get("events", [{}])[0].get("title", "无重大事件催化")
    return f"""
请为以下 A 股交易机会进行专业的风控分析：

**股票信息**
- 名称：{stock_name}
- 代码：{stock_symbol}
- 所属行业：{record.get('industry', 'N/A')}
- 交易策略模式：{mode_name}

**关键技术指标**
- 当前涨跌幅：{record.get('spot_pct', 0):.2f}%
- 当日成交额：{record.get('spot_amount', 0):.0f} 元
- 换手率：{record.get('spot_turnover', 0):.2f}%
- 近 10 日波动率：{record.get('feature_map', {}).get('volatility_10', 0):.2f}%
- 技术分值：{record.get('technical_score', 0):.1f}
- 行业分值：{record.get('industry_score', 0):.1f}
- 情绪分值：{record.get('sentiment_score', 0):.1f}

**风险计划建议**
- 建议仓位：{record.get('suggested_position_min', 0):.2%} - {record.get('suggested_position_max', 0):.2%}
- 参考止损位：{risk_plan.get('stop_loss_price', 0):.2f} 元 (止损 {risk_plan.get('stop_loss_pct', 0):.2%})
- 第一止盈位：{risk_plan.get('take_profit_price_1', 0):.2f} 元 (涨幅 {risk_plan.get('take_profit_pct_1', 0):.2%})
- 第二止盈位：{risk_plan.get('take_profit_price_2', 0):.2f} 元 (涨幅 {risk_plan.get('take_profit_pct_2', 0):.2%})
- 风险回报比：{risk_plan.get('risk_reward_ratio', 0):.1f}
- 执行建议：{risk_plan.get('action_bias', 'N/A')}

**最近事件**
{event_text}

请从以下几个方面出具分析（JSON 格式）：
1. stance：交易立场（看好/观望/看空）
2. key_insight：核心洞察（1-2 句）
3. execution_timing：执行节奏建议
4. risk_focus：主要风险点
5. position_sizing_rationale：仓位建议的依据
6. stop_loss_logic：止损逻辑说明
7. take_profit_strategy：止盈分批策略
8. confidence_level：整体置信度 (0.4-0.95)

返回纯 JSON 格式，无额外说明。
"""


def generate_ai_analysis_for_record(
    stock_name: str,
    stock_symbol: str,
    risk_plan: dict[str, Any],
    record: dict[str, Any],
    mode_name: str,
    ai_model: str = "gemini",
) -> dict[str, Any]:
    """
    为单只股票生成完整的 AI 分析

    Args:
        stock_name: 股票名称
        stock_symbol: 股票代码
        risk_plan: 风险计划（包含止损、止盈等）
        record: 股票记录（技术面、情绪面、行业等）
        mode_name: 策略模式名称
        ai_model: AI 模型选择 ("gemini" 或 "chatgpt")

    Returns:
        AI 分析结果对象
    """
    try:
        prompt = build_analysis_prompt(stock_name, stock_symbol, risk_plan, record, mode_name)

        if ai_model == "chatgpt":
            response_text = call_chatgpt_api(prompt)
        else:
            response_text = call_gemini_api(prompt)

        # 尝试解析 JSON 响应
        try:
            ai_result = json.loads(response_text)
        except json.JSONDecodeError:
            # 如果 AI 返回非 JSON，包装为默认结构
            ai_result = {
                "stance": "观望",
                "key_insight": response_text[:100],
                "confidence_level": 0.6,
            }

        return {
            "status": "ai_generated",
            "model": ai_model,
            "confidence": float(ai_result.get("confidence_level", 0.6)),
            "summary": ai_result.get("key_insight", "AI 分析已生成"),
            "highlights": [
                f"交易立场：{ai_result.get('stance', '观望')}",
                f"执行节奏：{ai_result.get('execution_timing', 'N/A')}",
                f"主要风险：{ai_result.get('risk_focus', 'N/A')}",
            ],
            "stance": ai_result.get("stance", "观望"),
            "execution_timing": ai_result.get("execution_timing", "N/A"),
            "risk_focus": ai_result.get("risk_focus", "N/A"),
            "position_sizing_rationale": ai_result.get("position_sizing_rationale", "N/A"),
            "stop_loss_logic": ai_result.get("stop_loss_logic", "N/A"),
            "take_profit_strategy": ai_result.get("take_profit_strategy", "N/A"),
            "next_step": "AI 分析已完成",
            "source": ai_model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "status": "ai_error",
            "model": ai_model,
            "error": str(e),
            "confidence": 0.3,
            "summary": f"AI 分析失败：{str(e)}",
            "highlights": ["请检查 API Key 和网络连接"],
            "source": ai_model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def enrich_snapshot_with_ai_analysis(
    snapshot: dict[str, Any],
    ai_model: str = "gemini",
    max_stocks: int = 10,
) -> dict[str, Any]:
    """
    用 AI 分析补充快照中的交易执行分析

    Args:
        snapshot: 原始快照
        ai_model: AI 模型选择
        max_stocks: 最多分析多少只股票（控制成本）

    Returns:
        增强后的快照
    """
    enriched_snapshot = snapshot.copy()
    enriched_snapshot["ai_analysis_updated_at"] = datetime.now(timezone.utc).isoformat()
    enriched_snapshot["ai_model"] = ai_model

    # 遍历候选池，为前 N 只股票生成 AI 分析
    candidate_pool = snapshot.get("candidate_pool", [])
    for i, record in enumerate(candidate_pool[:max_stocks]):
        try:
            symbol = record.get("symbol", "UNKNOWN")
            name = record.get("name", "Unknown")
            risk_plan = record.get("risk_plan", {})
            mode_id = record.get("mode", "balanced")

            # 从快照模式定义里找到模式名称
            mode_info = snapshot.get("strategy_modes", {}).get(mode_id, {})
            mode_name = mode_info.get("display_name", mode_id)

            # 生成 AI 分析
            ai_analysis = generate_ai_analysis_for_record(
                stock_name=name,
                stock_symbol=symbol,
                risk_plan=risk_plan,
                record=record,
                mode_name=mode_name,
                ai_model=ai_model,
            )

            record["ai_risk_analysis"] = ai_analysis
            print(f"✓ {name}({symbol}) AI 分析已生成")

        except Exception as e:
            print(f"✗ {record.get('name', 'Unknown')} 分析失败: {str(e)}")
            record["ai_risk_analysis"] = {
                "status": "error",
                "error": str(e),
            }

    return enriched_snapshot


if __name__ == "__main__":
    # 本地测试示例
    import sys

    if len(sys.argv) > 1:
        snapshot_path = sys.argv[1]
    else:
        snapshot_path = "data/processed/daily_candidates_latest.json"

    try:
        with open(snapshot_path, encoding="utf-8") as f:
            snapshot = json.load(f)
        print(f"加载快照：{snapshot_path}")

        # 用 AI 补充分析
        enriched = enrich_snapshot_with_ai_analysis(
            snapshot,
            ai_model="gemini",
            max_stocks=3,
        )

        # 输出到新文件
        output_path = snapshot_path.replace(".json", "_with_ai.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)
        print(f"✓ 已输出到：{output_path}")

    except FileNotFoundError:
        print(f"错误：找不到快照文件 {snapshot_path}")
    except Exception as e:
        print(f"错误：{str(e)}")
