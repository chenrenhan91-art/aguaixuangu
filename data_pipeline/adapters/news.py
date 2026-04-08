from datetime import datetime, timedelta, timezone

from data_pipeline.adapters.base import BaseAdapter


class DemoNewsAdapter(BaseAdapter[list[dict[str, object]]]):
    def fetch(self) -> list[dict[str, object]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "event_id": "evt-001",
                "publish_time": (now - timedelta(hours=6)).isoformat(),
                "source": "财联社",
                "title": "算力基础设施关注度提升",
                "event_type": "产业新闻",
                "sentiment": "positive",
                "summary": "产业景气预期改善，适合作为行业强度的辅助确认。",
                "symbols": ["000977.SZ", "603019.SH"],
            },
            {
                "event_id": "evt-002",
                "publish_time": (now - timedelta(hours=2)).isoformat(),
                "source": "上证报",
                "title": "北向资金回流科技成长板块",
                "event_type": "资金面",
                "sentiment": "positive",
                "summary": "资金面改善对成长风格形成边际强化。",
                "symbols": ["000977.SZ", "300308.SZ"],
            },
        ]

