from app.schemas.market import SectorSnapshot, TopSectorsResponse
from app.services.mock_data import demo_top_sectors, now_utc
from app.services.snapshot_store import load_latest_selection_snapshot


def list_top_sectors(limit: int = 5) -> TopSectorsResponse:
    snapshot = load_latest_selection_snapshot()
    if snapshot is not None:
        items = snapshot["top_sectors"][:limit]
        return TopSectorsResponse(
            items=[
                SectorSnapshot(
                    sector_code=item["sector_code"],
                    sector_name=item["sector_name"],
                    strength_score=item["strength_score"],
                    momentum_score=item["momentum_score"],
                    capital_consensus_score=item["capital_consensus_score"],
                    heat_score=item["heat_score"],
                )
                for item in items
            ],
            updated_at=snapshot["generated_at"],
        )

    sectors = demo_top_sectors()[:limit]
    return TopSectorsResponse(
        items=[
            SectorSnapshot(
                sector_code=sector.sector_code,
                sector_name=sector.sector_name,
                strength_score=sector.strength_score,
                momentum_score=sector.momentum_score,
                capital_consensus_score=sector.capital_consensus_score,
                heat_score=sector.heat_score,
            )
            for sector in sectors
        ],
        updated_at=now_utc(),
    )
