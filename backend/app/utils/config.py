"""
config.py
Environment-variable-based configuration using pydantic-settings.
All settings can be overridden via environment variables or a .env file.
"""
from __future__ import annotations
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Autonomous Data Scientist Agent"
    app_version: str = "2.0.0"
    debug: bool = False

    # Security
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    # NOTE: kept as a plain string field (not List[str]). pydantic-settings
    # tries to JSON-parse any List-typed field read from an env var/.env
    # file, which breaks on our plain comma-separated format
    # ("http://a,http://b"). Storing the raw string and exposing a parsed
    # `.cors_origins` property below avoids that entirely.
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias="CORS_ORIGINS",
    )

    # Database - SQLite default, set DATABASE_URL=postgresql://... for production
    database_url: str = "sqlite:///./data/agent.db"

    # LLM
    anthropic_api_key: Optional[str] = None
    llm_model: str = "claude-sonnet-4-6"
    llm_enabled: bool = True

    # File Handling
    upload_dir: str = "data/uploads"
    reports_dir: str = "data/reports"
    max_upload_size_mb: int = 50
    # Same JSON-parsing pitfall as cors_origins_raw above.
    allowed_extensions_raw: str = Field(
        default="csv,xls,xlsx,json,jsonl,parquet,feather,pdf,docx,txt,md,mp4",
        validation_alias="ALLOWED_EXTENSIONS",
    )

    # Agent
    default_test_size: float = 0.2
    default_cv_folds: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def allowed_extensions(self) -> List[str]:
        return [e.strip().lower() for e in self.allowed_extensions_raw.split(",") if e.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
