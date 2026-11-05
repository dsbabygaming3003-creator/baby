from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Provider secrets never belong in client builds."""

    model_config = SettingsConfigDict(env_prefix="TITAN_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./data/titan.db"
    api_key: str | None = None
    workspace_root: Path = Path("./data/workspaces")
    report_root: Path = Path("./data/reports")
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None
    github_token: str | None = None
    terminal_enabled: bool = True
    terminal_max_seconds: int = 20
    request_max_bytes: int = 1_000_000

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
