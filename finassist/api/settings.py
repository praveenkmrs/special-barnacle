from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FINASSIST_", env_file=".env", extra="ignore")

    db_path: Path = Field(default=Path.home() / ".finassist" / "finassist.db")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:5173"])

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
