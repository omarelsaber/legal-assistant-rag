"""
Configuration management for the Egyptian Law Assistant.

All settings are read from environment variables or a .env file.
Pydantic validates types and required secrets at startup — misconfiguration
fails immediately, not mid-request.

Provider architecture (LLM and Embeddings are independent):

  LLM_PROVIDER controls text generation:
    "groq"   → Groq Cloud API     — production free tier (recommended)
    "ollama" → local Ollama        — development
    "claude" → Anthropic API       — premium

  EMBEDDING_PROVIDER controls vector embeddings:
    "cohere" → Cohere Embed API    — production free tier (recommended)
    "ollama" → local Ollama        — development only (no GPU in cloud)

  The two settings are independent. The recommended production setup is:
    LLM_PROVIDER=groq  +  EMBEDDING_PROVIDER=cohere

  Why independent?
    Groq has no embedding API. Claude's embedding API is paid.
    Cohere's free tier (1,000 calls/month) covers demo and dev traffic.
    This separation lets us swap either provider without touching the other.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object — one source of truth for the entire application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: Literal["ollama", "claude", "groq"] = Field(
        default="groq",
        description="Active LLM backend. Switch via LLM_PROVIDER env var.",
    )

    # Ollama
    ollama_base_url: str  = Field(default="http://localhost:11434")
    ollama_model:    str  = Field(default="llama3")

    # Claude
    claude_api_key:  SecretStr | None = Field(default=None)
    claude_model:    str = Field(default="claude-sonnet-4-6")

    # Groq
    groq_api_key:    SecretStr | None = Field(default=None)
    groq_model:      str = Field(
        default="llama-3.3-70b-versatile",
        description="llama-3.3-70b-versatile recommended for Arabic legal text.",
    )

    # ── Embedding Provider (independent of LLM_PROVIDER) ─────────────────────
    embedding_provider: Literal["cohere", "ollama"] = Field(
        default="cohere",
        description=(
            "Backend for vector embeddings. Independent of LLM_PROVIDER. "
            "'cohere' = production cloud (free tier). "
            "'ollama' = local development only."
        ),
    )

    # Cohere (cloud embeddings — free tier)
    cohere_api_key:  SecretStr | None = Field(
        default=None,
        description=(
            "Cohere API key. Required when EMBEDDING_PROVIDER='cohere'. "
            "Free at https://dashboard.cohere.com/api-keys"
        ),
    )
    embedding_model: str = Field(
        default="embed-multilingual-v3.0",
        description=(
            "Cohere model name (production) or Ollama model name (local). "
            "embed-multilingual-v3.0: 1024-dim, Arabic-native, free tier."
        ),
    )
    embedding_input_type: Literal["search_document", "search_query"] = Field(
        default="search_query",
        description=(
            "Cohere input_type. MUST be 'search_document' during ingestion "
            "and 'search_query' during querying. The ingestion script overrides "
            "this via EMBEDDING_INPUT_TYPE=search_document in its environment."
        ),
    )
    embedding_dimension: int = Field(
        default=1024,
        gt=0,
        description="Output dimension. embed-multilingual-v3.0 = 1024.",
    )

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size:            int  = Field(default=1000, gt=0)
    chunk_overlap:         int  = Field(default=200,  ge=0)
    ingestion_batch_size:  int  = Field(default=10,   gt=0)

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = Field(default="localhost")
    chroma_port: int = Field(default=8000, gt=0, le=65535)

    # ── Cache ─────────────────────────────────────────────────────────────────
    ingestion_cache_dir:        str = Field(default="data/cache")
    query_embedding_cache_size: int = Field(default=256, gt=0)

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host:   str  = Field(default="0.0.0.0")
    api_port:   int  = Field(default=8000, gt=0, le=65535)
    api_reload: bool = Field(default=False)

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri:    str = Field(default="http://localhost:5000")
    mlflow_experiment_name: str = Field(default="egyptian-law-rag")

    # ── Ragas Thresholds ──────────────────────────────────────────────────────
    ragas_faithfulness_threshold:      float = Field(default=0.7, ge=0.0, le=1.0)
    ragas_answer_relevancy_threshold:  float = Field(default=0.6, ge=0.0, le=1.0)
    ragas_context_recall_threshold:    float = Field(default=0.6, ge=0.0, le=1.0)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_less_than_chunk_size(cls, v: int, info: object) -> int:
        data = getattr(info, "data", {})
        if v >= data.get("chunk_size", 1000):
            raise ValueError(
                f"chunk_overlap ({v}) must be less than chunk_size "
                f"({data.get('chunk_size', 1000)})."
            )
        return v

    @model_validator(mode="after")
    def validate_all_provider_keys(self) -> "Settings":
        """Fail fast at startup if any active provider is missing its API key."""
        errors: list[str] = []

        if self.llm_provider == "claude" and not self.claude_api_key:
            errors.append(
                "CLAUDE_API_KEY is required when LLM_PROVIDER='claude'."
            )
        if self.llm_provider == "groq" and not self.groq_api_key:
            errors.append(
                "GROQ_API_KEY is required when LLM_PROVIDER='groq'. "
                "Free at https://console.groq.com/keys"
            )
        if self.embedding_provider == "cohere" and not self.cohere_api_key:
            errors.append(
                "COHERE_API_KEY is required when EMBEDDING_PROVIDER='cohere'. "
                "Free at https://dashboard.cohere.com/api-keys"
            )

        if errors:
            raise ValueError(
                "Missing required API keys:\n" + "\n".join(f"  • {e}" for e in errors)
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.
    Call get_settings.cache_clear() in tests before constructing overrides.
    """
    return Settings()


# Module-level singleton — the standard import for application code.
settings: Settings = get_settings()