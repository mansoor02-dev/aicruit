"""
Validated environment configuration for the Resume Parser service.

All settings are loaded from environment variables with sensible defaults.
Uses Pydantic BaseSettings for validation and type coercion.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Resume Parser service configuration."""

    # ── LLM Provider ──────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model identifier",
    )
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_output_tokens: int = Field(default=4096, ge=256, le=65536)
    llm_timeout_seconds: float = Field(default=60.0, ge=5.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    # ── OpenRouter fallback (retained for backward compatibility) ─────────
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    llm_fallback_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
    )

    # ── PDF Processing ────────────────────────────────────────────────────
    max_file_size_mb: int = Field(default=10, ge=1, le=50)
    max_page_count: int = Field(default=20, ge=1, le=100)
    min_chars_per_page: int = Field(
        default=50,
        description="Pages with fewer chars are flagged as scanned/empty",
    )
    ocr_enabled: bool = Field(
        default=True,
        description="Whether to attempt OCR on scanned pages",
    )
    ocr_dpi: int = Field(default=200, ge=72, le=600)
    processing_timeout_seconds: float = Field(default=120.0, ge=10.0)

    # ── Text Normalization ────────────────────────────────────────────────
    max_input_tokens: int = Field(
        default=6000,
        description="Maximum word count sent to LLM (budget for gemini-2.5-flash context)",
    )

    # ── Concurrency & Caching ─────────────────────────────────────────────
    max_concurrent_llm_calls: int = Field(default=4, ge=1, le=20)
    cache_enabled: bool = Field(default=True)
    cache_max_size: int = Field(default=128, ge=0)
    cache_schema_version: str = Field(
        default="v1",
        description="Bump to invalidate all cached results on schema change",
    )

    # ── Database ──────────────────────────────────────────────────────────
    database_url: Optional[str] = Field(default=None)
    db_user: str = Field(default="admin")
    db_pass: str = Field(default="admin123")
    db_host: str = Field(default="localhost")
    db_port: str = Field(default="5432")
    db_name: str = Field(default="aicruit")

    # ── Service Integration ───────────────────────────────────────────────
    file_service_url: str = Field(default="http://localhost:8005")
    frontend_origins: str = Field(default="http://localhost:3000")
    app_url: str = Field(default="http://localhost:3000")

    # ── Derived ───────────────────────────────────────────────────────────
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_pass}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def frontend_origins_list(self) -> list[str]:
        origins = [o.strip() for o in self.frontend_origins.split(",") if o.strip()]
        return origins if origins else ["*"]

    @field_validator("gemini_api_key")
    @classmethod
    def _warn_empty_gemini(cls, v: str) -> str:
        # Don't raise — allow startup for tests and score-fit-only use
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings instance, cached after first load."""
    return Settings()
