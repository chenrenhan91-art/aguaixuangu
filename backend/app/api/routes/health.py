from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.health import HealthCheckResponse


router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
def healthcheck() -> HealthCheckResponse:
    return HealthCheckResponse(status="ok", timestamp=datetime.now(timezone.utc))

