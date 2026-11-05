"""TITAN OMEGA INFINITY V18 — runtime configuration.

All settings are environment-driven so that the same image can run in
sandbox, CI and production. Secrets are NEVER defaulted to a real value:
if a provider key is absent the gateway reports `no_key` rather than
silently using a placeholder.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TITAN_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- identity -------------------------------------------------------
    app_name: str = "TITAN OMEGA INFINITY"
    version: str = "18.0.0"
    edition: str = "V18 — ULTIMATE SUPREME BUILD"
    env: str = "development"
    debug: bool = True

    # ---- server ---------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # ---- storage --------------------------------------------------------
    data_dir: Path = Field(default_factory=lambda: Path(os.environ.get("TITAN_DATA_DIR", REPO_ROOT / "data")))
    database_url: str = Field(default_factory=lambda: os.environ.get("TITAN_DATABASE_URL", ""))
    sql_echo: bool = False

    # ---- security -------------------------------------------------------
    jwt_secret: str = Field(default_factory=lambda: os.environ.get("TITAN_JWT_SECRET", "titan-dev-secret-change-me"))
    jwt_algorithm: str = "HS256"
    jwt_ttl_seconds: int = 60 * 60 * 12
    scrypt_n: int = 1 << 14
    scrypt_r: int = 8
    scrypt_p: int = 1
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 40

    # ---- egress ---------------------------------------------------------
    # Hosts the deployment is permitted to contact. When empty, the SSRF
    # guard still applies its private-range rejection but allows public hosts.
    egress_allowlist: List[str] = Field(default_factory=list)

    # ---- model gateway --------------------------------------------------
    provider_keys: dict = Field(default_factory=dict)
    provider_base_urls: dict = Field(default_factory=dict)
    gateway_timeout_seconds: int = 90
    gateway_max_retries: int = 2
    gateway_default_model: str = "gpt-4o-mini"
    allow_mock_provider: bool = True

    # ---- sandbox --------------------------------------------------------
    sandbox_root: Path = Field(default_factory=lambda: Path(os.environ.get("TITAN_SANDBOX_ROOT", "/tmp/titan-sandbox")))
    sandbox_cpu_seconds: int = 20
    sandbox_memory_mb: int = 1024
    sandbox_max_output_bytes: int = 256 * 1024
    sandbox_timeout_seconds: int = 30
    sandbox_max_processes: int = 64
    command_allowlist: List[str] = Field(
        default_factory=lambda: [
            "ls", "pwd", "echo", "cat", "head", "tail", "wc", "find", "grep", "rg",
            "git", "python3", "pip", "node", "npm", "make", "cmake", "gradle",
            "javac", "java", "kotlinc", "aapt2", "d8", "zip", "unzip", "sha256sum",
            "stat", "df", "du", "ps", "env", "which", "date", "uname", "sort", "uniq",
            "sed", "awk", "jq", "diff", "tree", "mkdir", "cp", "mv", "rm", "touch",
        ]
    )

    # ---- research -------------------------------------------------------
    research_request_timeout: int = 20
    research_max_results_per_connector: int = 15
    research_max_document_chars: int = 20000
    research_store_full_text: bool = False

    # ---- workflows ------------------------------------------------------
    workflow_max_parallel: int = 4
    workflow_step_timeout_seconds: int = 300

    # ---- embeddings / rag ----------------------------------------------
    embedding_dim: int = 384
    rag_top_k: int = 8
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 120

    @field_validator("cors_origins", "egress_allowlist", "command_allowlist", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.data_dir / 'titan.db'}"

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
