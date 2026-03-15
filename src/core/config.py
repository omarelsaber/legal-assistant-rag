"""
Configuration management for the Egyptian Law Assistant.

All settings are read from environment variables or a .env file.
Pydantic validates types and required secrets at application startup,
so misconfiguration fails immediately — not mid-request.

Usage:
    from src.core.config import settings
    print(settings.llm_provider)
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object for the entire application.

    Reads from environment variables and a .env file.
    All LLM-provider-specific secrets are validated for mutual
    consistency via the model validator below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Silently ignore unknown env vars rather than raising
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: Literal["ollama", "claude"] = Field(
        default="ollama",
        description="Active LLM backend. Switch via LLM_PROVIDER env var.",
    )

    # Ollama (local inference)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the running Ollama server.",
    )
    ollama_model: str = Field(
        default="llama3",
        description="Ollama model tag to use for generation.",
    )

    # Claude (Anthropic API)
    claude_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key. Required when llm_provider='claude'.",
    )
    claude_model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model identifier.",
    )

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = Field(
        default="bge-m3",
        description="Embedding model name served by Ollama.",
    )
    embedding_dimension: int = Field(
        default=768,
        gt=0,
        description="Output dimension of the embedding model. Must match ChromaDB collection.",
    )

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = Field(
        default=512,
        gt=0,
        description="Token/character budget per document chunk.",
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        description="Overlap between consecutive chunks to preserve cross-boundary context.",
    )
    ingestion_batch_size: int = Field(
        default=10,
        gt=0,
        description="Number of documents processed per batch during streaming ingestion.",
    )

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8000, gt=0, le=65535)

    # ── Embedding Cache ───────────────────────────────────────────────────────
    ingestion_cache_dir: str = Field(
        default="data/cache",
        description="Disk path for LlamaIndex IngestionCache (persists between restarts).",
    )
    query_embedding_cache_size: int = Field(
        default=256,
        gt=0,
        description="Max entries in the in-memory LRU cache for query embeddings.",
    )

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8080, gt=0, le=65535)
    api_reload: bool = Field(
        default=False,
        description="Enable uvicorn hot-reload. True only in local development.",
    )

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = Field(default="http://localhost:5000")
    mlflow_experiment_name: str = Field(default="egyptian-law-rag")

    # ── Ragas Evaluation Thresholds ───────────────────────────────────────────
    ragas_faithfulness_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    ragas_answer_relevancy_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    ragas_context_recall_threshold: float = Field(default=0.6, ge=0.0, le=1.0)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_must_be_less_than_chunk_size(cls, v: int, info: object) -> int:
        """Ensure chunk_overlap < chunk_size to prevent degenerate chunking."""
        # info.data contains already-validated fields
        data = getattr(info, "data", {})
        chunk_size = data.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({v}) must be strictly less than chunk_size ({chunk_size})."
            )
        return v

    @model_validator(mode="after")
    def claude_key_required_when_provider_is_claude(self) -> "Settings":
        """
        Fail fast at startup if Claude is selected but no API key is provided.
        Catching this here prevents a cryptic AuthenticationError mid-request.
        """
        if self.llm_provider == "claude" and not self.claude_api_key:
            raise ValueError(
                "CLAUDE_API_KEY must be set when LLM_PROVIDER='claude'. "
                "Add it to your .env file or environment."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using lru_cache ensures the .env file is read exactly once per process.
    In tests, call get_settings.cache_clear() before constructing override instances.
    """
    return Settings()


# Module-level singleton — the standard import for all application code.
# Tests that need overrides should use get_settings() with cache_clear(),
# not import this directly.
settings: Settings = get_settings()