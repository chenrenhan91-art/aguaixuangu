from fastapi import APIRouter, Query

from app.schemas.market import TopSectorsResponse
from app.services.sectors import list_top_sectors


router = APIRouter()


@router.get("/top", response_model=TopSectorsResponse)
def top_sectors(limit: int = Query(default=5, ge=1, le=20)) -> TopSectorsResponse:
    return list_top_sectors(limit=limit)

