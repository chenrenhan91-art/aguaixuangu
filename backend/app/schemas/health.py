from datetime import datetime

from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime

