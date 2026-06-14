"""Centralized configuration.

OWNER: Person A
SPRINT CONCEPTS: Code-Quality (typed config, single source of truth).
CONSUMES: ``pydantic-settings``, ``python-dotenv``.
PROVIDES: ``Settings`` dataclass, ``settings`` singleton.

All knobs live here. Every other module should import ``settings`` instead
of reading ``os.environ`` directly. This keeps things testable and swappable.

We use ``pydantic-settings`` so values are typed, validated, and documented.
Override anything via environment variables or a local ``.env`` file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed runtime configuration.

    Values are read from (in order of priority):
      1. Process environment variables
      2. `.env` file in the project root
      3. Defaults below
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------- OpenRouter ----------------------------------------------------
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_app_name: str = Field(default="design-analysis-suite")
    openrouter_site_url: str = Field(default="https://example.com")

    # -------- Default models ------------------------------------------------
    default_vision_model: str = Field(default="openai/gpt-4o-mini")
    default_text_model: str = Field(default="openai/gpt-4o-mini")
    # Why 0.2 (NOT the chat default 0.7-1.0):
    #   * Every agent call is a STRUCTURED-OUTPUT call (json_schema mode).
    #   * Higher temperature breaks JSON adherence and inflates eval flake.
    #   * Cache hit-rate plummets above ~0.4 (the model picks different words
    #     each call -> different prompt-hash inputs are fine, but different
    #     OUTPUTS for the same inputs makes the cache useless for replay).
    #   * Market-research's brainstorm step is the ONE place where you might
    #     want 0.6+; override per-call via deps.llm.complete(..., temperature=...)
    #     instead of changing this default.
    default_temperature: float = Field(default=0.2)
    default_max_tokens: int = Field(default=2048)

    # -------- Web search ----------------------------------------------------
    tavily_api_key: str = Field(default="")

    # -------- Vector store / RAG -------------------------------------------
    vector_store_dir: Path = Field(default=PROJECT_ROOT / "data" / "vector_store")
    vector_collection: str = Field(default="design_references")
    clip_model: str = Field(default="ViT-B-32")
    clip_pretrained: str = Field(default="laion2b_s34b_b79k")

    # -------- Storage -------------------------------------------------------
    upload_dir: Path = Field(default=PROJECT_ROOT / "data" / "uploads")
    reference_dir: Path = Field(default=PROJECT_ROOT / "data" / "reference")
    report_dir: Path = Field(default=PROJECT_ROOT / "data" / "reports")
    cache_dir: Path = Field(default=PROJECT_ROOT / "data" / "cache")

    # -------- Observability (Sprint 5) -------------------------------------
    langchain_tracing_v2: bool = Field(default=False)
    langchain_api_key: str = Field(default="")
    langchain_project: str = Field(default="design-analysis-suite")

    # -------- MCP (Sprint 4) -----------------------------------------------
    mcp_transport: str = Field(default="stdio")

    # -------- Cost layer (Sprint 5) ----------------------------------------
    cache_disabled: bool = Field(default=False)

    # -------- Slice toggle -------------------------------------------------
    # When False, AgentDeps wires fakes (no keys). When True, real impls.
    use_real: bool = Field(default=False)

    # -------- App -----------------------------------------------------------
    log_level: str = Field(default="INFO")
    app_env: str = Field(default="dev")

    # ------------------------------------------------------------------ utils
    def ensure_dirs(self) -> None:
        """Create all data directories on first use."""
        for p in (
            self.vector_store_dir,
            self.upload_dir,
            self.reference_dir,
            self.report_dir,
            self.cache_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings accessor.

    Cached so we read the .env file only once per process.
    """
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
