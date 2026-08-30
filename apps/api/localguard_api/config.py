"""Environment-backed application configuration with fail-closed provider selection."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets remain in the environment and are never logged."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_origin: str = "http://localhost:3000"
    api_public_origin: str = "http://localhost:3000"
    allowed_hosts: Annotated[tuple[str, ...], NoDecode] = ("localhost", "127.0.0.1", "api")
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://localguard:localguard@localhost:5432/localguard"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    outbox_poll_seconds: float = Field(default=2.0, ge=0.25, le=60)
    outbox_claim_ttl_seconds: int = Field(default=60, ge=10, le=600)
    outbox_delivery_timeout_seconds: int = Field(default=900, ge=300, le=3600)
    cleanup_poll_seconds: float = Field(default=5.0, ge=0.25, le=300)

    upload_root: Path = Path(".localguard/uploads")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    max_pdf_pages: int = Field(default=100, ge=1, le=100)
    max_docx_paragraphs: int = Field(default=2500, ge=1, le=5000)
    max_text_lines: int = Field(default=5000, ge=1, le=20_000)
    max_extracted_characters: int = Field(default=500_000, ge=1, le=1_000_000)
    max_docx_entries: int = Field(default=2500, ge=1, le=5000)
    max_docx_expanded_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_docx_compression_ratio: float = Field(default=100.0, ge=1, le=1000)

    session_cookie_name: str = "localguard_session"
    session_cookie_secure: bool = False
    session_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    csrf_header_name: str = "X-CSRF-Token"
    csrf_cookie_name: str = "localguard_csrf"
    login_window_seconds: int = Field(default=900, ge=60, le=3600)
    login_max_failures: int = Field(default=5, ge=1, le=20)
    bootstrap_admin_password: SecretStr | None = None
    bootstrap_reviewer_password: SecretStr | None = None
    bootstrap_viewer_password: SecretStr | None = None

    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "qwen3:1.7b-q4_K_M"
    ollama_embed_model: str = "all-minilm:22m-l6-v2-fp16"
    model_context_tokens: int = Field(default=4096, ge=1024, le=8192)
    model_max_output_tokens: int = Field(default=512, ge=64, le=2048)
    model_lock_ttl_seconds: int = Field(default=360, ge=30, le=900)
    model_http_timeout_seconds: float = Field(default=300.0, ge=5, le=300)
    ai_provider: Literal["ollama", "deterministic"] = "ollama"
    embedding_provider: Literal["ollama", "deterministic"] = "ollama"
    allow_test_providers: bool = False
    retrieval_limit: int = Field(default=8, ge=1, le=20)
    retrieval_candidate_limit: int = Field(default=24, ge=5, le=100)
    retrieval_min_score: float = Field(default=0.012, ge=0, le=1)
    retrieval_min_vector_similarity: float = Field(default=0.35, ge=-1, le=1)
    retrieval_min_text_score: float = Field(default=0.05, ge=0, le=1)

    proposal_ttl_minutes: int = Field(default=1440, ge=5, le=10_080)
    mcp_bind_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8001, ge=1024, le=65_535)
    mcp_allowed_origins: Annotated[tuple[str, ...], NoDecode] = ("http://localhost:3000",)
    mcp_bootstrap_token: SecretStr | None = None
    mcp_bootstrap_token_ttl_days: int = Field(default=30, ge=1, le=365)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("mcp_allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip().rstrip("/") for part in value.split(",") if part.strip())
        return value

    @field_validator("app_origin", "api_public_origin", "ollama_base_url")
    @classmethod
    def reject_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def enforce_runtime_boundaries(self) -> Settings:
        if self.ai_provider != self.embedding_provider:
            raise ValueError("AI_PROVIDER and EMBEDDING_PROVIDER must select the same runtime")
        uses_deterministic = self.ai_provider == "deterministic"
        if uses_deterministic and not (self.app_env == "test" and self.allow_test_providers):
            raise ValueError("deterministic providers are permitted only in explicit test mode")
        if self.model_lock_ttl_seconds < self.model_http_timeout_seconds + 30:
            raise ValueError("MODEL_LOCK_TTL_SECONDS must exceed the HTTP timeout by 30 seconds")
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError("SESSION_COOKIE_SECURE must be true in production")
        if not self.allowed_hosts:
            raise ValueError("ALLOWED_HOSTS must contain at least one host")
        if not self.mcp_allowed_origins:
            raise ValueError("MCP_ALLOWED_ORIGINS must contain at least one exact origin")
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"

    @property
    def checkpoint_database_url(self) -> str:
        """Return a psycopg URL accepted by LangGraph's PostgreSQL saver."""

        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    """Testing hook for isolated environment configuration."""

    get_settings.cache_clear()
