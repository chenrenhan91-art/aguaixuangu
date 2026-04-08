from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "A股AI选股工具"
    api_v1_prefix: str = "/api"
    frontend_origin: str = "http://localhost:5173"
    environment: str = "development"
    default_hold_days: int = 5
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-preview"
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[3] / "data"
    )

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_prefix="A_SHARE_",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [self.frontend_origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
