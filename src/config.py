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
    # GPT-5 Mini is the project default (set Aug 2025 launch on
    # OpenRouter; we adopted June 2026 after the visual self-heal data
    # showed gpt-4o-mini retrying ~95% of multimodal runs).
    #   * Better instruction-following + structured-output adherence
    #     than gpt-4o-mini -> visual self-heal almost never fires.
    #   * Native multimodal (image + text) on the same endpoint.
    #   * 400K context window so multi-frame runs fit comfortably.
    #   * $0.25 / $2.00 per M tokens (vs $0.15 / $0.60 for
    #     gpt-4o-mini) but that headline diff understates the real
    #     win: fewer retries means fewer doubled visual calls.
    # Override at runtime by setting DEFAULT_VISION_MODEL or
    # DEFAULT_TEXT_MODEL in .env / Spaces secrets. Cheaper alternatives:
    #   - openai/gpt-5-nano        ($0.05 / $0.40, weaker reasoning)
    #   - openai/gpt-4o-mini       ($0.15 / $0.60, more retries)
    # Stronger alternatives:
    #   - anthropic/claude-3.5-sonnet ($3.00 / $15.00, gold-standard vision)
    #   - openai/gpt-5             ($1.25 / $10.00, full GPT-5)
    default_vision_model: str = Field(default="openai/gpt-5-mini")
    default_text_model: str = Field(default="openai/gpt-5-mini")
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
    # LOGIC: 8192 leaves room for both the JSON output AND the reasoning
    # tokens that GPT-5 / o1 / o3 burn before producing visible content.
    # Empirical floor on multi-image multimodal calls:
    #   * 2048 -> truncated mid-string (Pydantic "EOF while parsing")
    #   * 4096 -> empty content on 3 of 4 parallel agents
    #   * 8192 -> all 4 agents complete cleanly (~1.5 KB output, ~0.5 KB
    #     reasoning at effort=minimal, ~0.5 KB system prompt overhead)
    # The OpenRouter client also auto-bumps to 8192 specifically for
    # reasoning models even when a smaller value is set here, so this
    # ceiling protects non-reasoning model budgets.
    default_max_tokens: int = Field(default=8192)

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
    # Logs always tee to a file under <project>/data/logs so users (and
    # judges) never have to copy-paste from the console. The path is
    # surfaced in the Settings tab and printed at launch. Set
    # ``LOG_TO_FILE=0`` in .env to opt out (useful in CI / headless
    # workers where the orchestrator already captures stdout).
    log_dir: Path = Field(default=PROJECT_ROOT / "data" / "logs")
    log_to_file: bool = Field(default=True)

    # ------------------------------------------------------------------ utils
    def ensure_dirs(self) -> None:
        """Create all data directories on first use."""
        for p in (
            self.vector_store_dir,
            self.upload_dir,
            self.reference_dir,
            self.report_dir,
            self.cache_dir,
            self.log_dir,
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
