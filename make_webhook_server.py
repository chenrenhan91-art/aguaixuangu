"""
Make.com Webhook 集成服务
提供 HTTP 端点供 make.com 调用，生成并返回 AI 增强的快照
"""

import json
import os
from pathlib import Path

from flask import Flask, jsonify, request

from data_pipeline.ai_analysis_service import enrich_snapshot_with_ai_analysis

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health_check():
    """健康检查端点"""
    return jsonify({"status": "ok", "service": "ai_analysis_webhook"}), 200


@app.route("/api/enrich_snapshot", methods=["POST"])
def enrich_snapshot():
    """
    接收快照并用 AI 分析补充
    
    请求体：
    {
        "snapshot_path": "data/processed/daily_candidates_latest.json",
        "ai_model": "gemini",  # 或 "chatgpt"
        "max_stocks": 10
    }
    
    返回：
    {
        "success": true,
        "output_path": "...",
        "candidate_count": 15,
        "ai_enriched_count": 10,
        "ai_model": "gemini"
    }
    """
    try:
        payload = request.get_json() or {}
        snapshot_path = payload.get("snapshot_path", "data/processed/daily_candidates_latest.json")
        ai_model = payload.get("ai_model", "gemini")
        max_stocks = payload.get("max_stocks", 10)

        # 读取快照
        if not os.path.exists(snapshot_path):
            return (
                jsonify({"success": False, "error": f"快照文件不存在: {snapshot_path}"}),
                404,
            )

        with open(snapshot_path, encoding="utf-8") as f:
            snapshot = json.load(f)

        # 用 AI 补充分析
        enriched_snapshot = enrich_snapshot_with_ai_analysis(
            snapshot,
            ai_model=ai_model,
            max_stocks=max_stocks,
        )

        # 输出到新文件或覆盖
        output_path = snapshot_path.replace(".json", "_ai_enriched.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(enriched_snapshot, f, ensure_ascii=False, indent=2)

        return jsonify(
            {
                "success": True,
                "output_path": str(Path(output_path).absolute()),
                "candidate_count": len(enriched_snapshot.get("candidate_pool", [])),
                "ai_enriched_count": max_stocks,
                "ai_model": ai_model,
                "message": f"已生成 {max_stocks} 只股票的 AI 分析",
            }
        ), 200

    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "请求体不是有效的 JSON"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/batch_analysis", methods=["POST"])
def batch_analysis():
    """
    批量分析单只股票（来自 make.com 的数据）
    
    请求体：
    {
        "records": [
            {
                "symbol": "603629",
                "name": "利通电子",
                "mode_name": "综合研判",
                "risk_plan": {...},
                "record": {...}
            }
        ],
        "ai_model": "gemini"
    }
    
    返回分析结果列表
    """
    try:
        payload = request.get_json() or {}
        records = payload.get("records", [])
        ai_model = payload.get("ai_model", "gemini")

        results = []
        for item in records:
            from data_pipeline.ai_analysis_service import generate_ai_analysis_for_record

            analysis = generate_ai_analysis_for_record(
                stock_name=item.get("name", "Unknown"),
                stock_symbol=item.get("symbol", "000000"),
                risk_plan=item.get("risk_plan", {}),
                record=item.get("record", {}),
                mode_name=item.get("mode_name", "balanced"),
                ai_model=ai_model,
            )
            results.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("name"),
                    "analysis": analysis,
                }
            )

        return jsonify(
            {
                "success": True,
                "count": len(results),
                "results": results,
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
