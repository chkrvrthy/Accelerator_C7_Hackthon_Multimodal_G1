"""Real ``LLMClient`` over OpenRouter using the OpenAI SDK.

OWNER: Person A
SPRINT CONCEPTS:
    - Sprint 1: OpenAI Chat Completion standard, JSON-schema mode.
CONSUMES: ``src.config.settings`` + (lazily) the ``openai`` SDK.
PROVIDES: ``OpenRouterClient`` (implements ``LLMClient``), singleton accessor.

WHY YOU CARE
------------
This is the file judges open when they ask "how do you call the LLM?". It is
the single place where text prompts become typed Python objects. Every other
LLM call in the system flows through here (or its multimodal sibling).

LOGIC OUTLINE
-------------
1. Build an ``openai.OpenAI`` client pointed at OpenRouter's base URL with
   ``HTTP-Referer`` and ``X-Title`` headers (OpenRouter's analytics tier).
2. ``complete`` derives a JSON schema from the requested Pydantic model and
   passes it via ``response_format={"type":"json_schema", ...}``.
3. Validate the response and return ``schema(**parsed)``.
4. Wrap with ``cost.cached`` so identical prompts hit the disk cache.

TEACHING NOTES (mentor's voice)
-------------------------------
We pick ONE library — the OpenAI SDK — and point it at ANY backend. OpenRouter
speaks OpenAI's wire format, so there is nothing to learn beyond what you
already know. Resist the temptation to bring in ``litellm`` or ``instructor``;
each adds a layer judges have to ask "what does that do?".

JSON-schema mode is the demo's super-power. Without it we'd spend hours
chasing markdown-wrapped JSON and trailing commas. With it, the model is
forced into our exact shape; ``pydantic.model_validate`` confirms it.

DEFINITION OF DONE (mark each one when the function is wired)
-------------------------------------------------------------
[ ] ``_client()`` lazy-builds the SDK with base_url + headers.
[ ] ``complete()`` returns a validated ``schema`` instance for any of:
      VisualAnalysis, UXCritique, AccessibilityReport, MarketResearch,
      BrandConsistency, DesignReport.
[ ] Cache hit on the second identical call (verify by deleting then
    re-running with ``CACHE_DISABLED=0``).
[ ] ``test_openrouter_complete_returns_visual_analysis`` passes with
    ``OPENROUTER_API_KEY`` set.
[ ] On rate limit, three exponential-backoff retries before re-raising.

DO NOT
------
- Do not import torch / transformers here.
- Do not catch broad ``Exception`` — re-raise ``openai.OpenAIError`` so the
  cost layer above can see it.
- Do not log full prompts at INFO; they pollute LangSmith UI. DEBUG only.
- Do not hand-roll JSON parsing — ``schema.model_validate`` already does it.
"""

from __future__ import annotations

import json
import random
import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from src.config import Settings, settings
from src.llm.cost import cached
from src.utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

log = get_logger(__name__)

# LOGIC: only retry on transient transport-layer errors. Auth / 4xx are
# user-actionable and re-raise immediately so the operator sees them.
_RETRYABLE_OPENAI_ERRORS = ("RateLimitError", "APIConnectionError", "APITimeoutError")
_MAX_RETRIES = 3


class OpenRouterClient:
    """Real ``LLMClient`` — OpenAI SDK pointed at OpenRouter."""

    def __init__(self, cfg: Settings | None = None) -> None:
        # NOTE: settings is a singleton; injecting one for tests is a clean
        # extension point you almost never use in production.
        self.settings = cfg or settings
        self._sdk: OpenAI | None = None

    # ------------------------------------------------------------------
    # Public API (LLMClient protocol)
    # ------------------------------------------------------------------
    @cached
    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        """Run a chat.completions call that MUST validate against ``schema``.

        Args:
            system: System prompt.
            user: User content.
            schema: Pydantic v2 model class. Used for response_format AND for
                post-call validation.
            model: Override default text model. None → ``settings.default_text_model``.
            temperature: Override default temperature.

        Returns:
            A validated instance of ``schema``.

        Raises:
            ValueError: when the model returns malformed JSON we cannot recover from.
            openai.OpenAIError: on transport / auth / rate-limit failures
                (after exhausting retries).
        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self._chat_with_schema(
            messages=messages,
            schema=schema,
            model=model or self.settings.default_text_model,
            temperature=(
                temperature if temperature is not None else self.settings.default_temperature
            ),
        )

    # ------------------------------------------------------------------
    # Shared chat-with-schema worker (used by complete + by multimodal)
    # ------------------------------------------------------------------
    def _chat_with_schema(
        self,
        *,
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        model: str,
        temperature: float | None = None,
    ) -> BaseModel:
        """Core call. Handles retries + json_schema → json_object fallback.

        Public-API consumers call ``complete`` (text) or ``OpenRouterVision.analyze``
        (multimodal); this method is shared so retry / fallback / validation logic
        is in exactly one place.
        """
        rf = self._schema_payload(schema)
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._client().chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format=rf,
                    temperature=temperature,
                    max_tokens=self.settings.default_max_tokens,
                )
                raw = resp.choices[0].message.content or ""
                return self._validate_or_fallback(raw, schema)

            except Exception as e:
                last_exc = e
                # LOGIC: only retry on transient transport errors. Auth / 4xx
                # are user-actionable and surface immediately.
                if type(e).__name__ in _RETRYABLE_OPENAI_ERRORS and attempt < _MAX_RETRIES - 1:
                    delay = (1.5**attempt) + random.random() * 0.2
                    log.warning(
                        "openrouter: %s on attempt %d/%d, retrying in %.1fs",
                        type(e).__name__,
                        attempt + 1,
                        _MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                # LOGIC: providers occasionally reject the strict json_schema mode;
                # downgrade ONCE to plain json_object before giving up.
                if type(e).__name__ == "BadRequestError" and rf["type"] == "json_schema":
                    log.warning("openrouter: json_schema rejected, retrying with json_object")
                    rf = {"type": "json_object"}
                    messages = self._inject_schema_hint(messages, schema)
                    continue
                raise

        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _client(self) -> OpenAI:
        """Lazy-construct the OpenAI SDK with OpenRouter base URL + headers."""
        if self._sdk is not None:
            return self._sdk
        if not self.settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Either export it, set it in .env, "
                "or run with USE_REAL=0 to use the FakeLLM."
            )
        # LOGIC: lazy import keeps non-Person-A slices import-cheap. Other
        # owners type-check this module without needing the openai SDK.
        from openai import OpenAI

        self._sdk = OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": self.settings.openrouter_site_url,
                "X-Title": self.settings.openrouter_app_name,
            },
        )
        return self._sdk

    @staticmethod
    def _schema_payload(schema: type[BaseModel]) -> dict[str, Any]:
        """Build the OpenRouter ``response_format`` payload for a Pydantic model.

        ``strict: True`` makes the model emit *only* JSON; without it providers
        occasionally add prose that breaks ``model_validate_json``.
        """
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": True,
            },
        }

    @staticmethod
    def _inject_schema_hint(
        messages: list[dict[str, Any]], schema: type[BaseModel]
    ) -> list[dict[str, Any]]:
        """Append the JSON schema as a textual hint when falling back to json_object."""
        # LOGIC: in fallback mode the SDK only gets `{"type":"json_object"}`,
        # no schema. So we paste the schema into the system prompt.
        out = [dict(m) for m in messages]
        if out and out[0].get("role") == "system":
            sys_content = out[0].get("content", "") or ""
            schema_blob = json.dumps(schema.model_json_schema())
            out[0][
                "content"
            ] = f"{sys_content}\n\nReturn ONLY a JSON object that conforms to this schema:\n{schema_blob}"
        return out

    @staticmethod
    def _validate_or_fallback(raw: str, schema: type[BaseModel]) -> BaseModel:
        """Validate JSON; if the model wrapped it in markdown, strip and retry once."""
        if not raw:
            raise ValueError(f"OpenRouter returned empty content for {schema.__name__}")
        try:
            return schema.model_validate_json(raw)
        except ValidationError:
            # LOGIC: occasional provider drift wraps JSON in ```json ... ```.
            # Strip code fences and retry ONCE before giving up.
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```", 2)[-1].strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()
            return schema.model_validate_json(cleaned)


def get_openrouter_client() -> OpenRouterClient:
    """Module-level singleton accessor.

    HINT: settings is already lru_cached, so the only thing to memoize here
    is the SDK client itself, which ``OpenRouterClient`` already does on
    ``self._sdk``. A plain singleton is enough.
    """
    # TODO(person-a, optional): wrap with @lru_cache(maxsize=1) if you find
    # yourself constructing this in a hot path. The default test path
    # constructs it once per pytest session — fine.
    return OpenRouterClient()


if __name__ == "__main__":  # pragma: no cover
    # Smoke test — `python -m src.llm.openrouter_client --smoke`.
    # HINT: keep this tiny; the real tests live in
    #       tests/person_a/test_openrouter.py with @pytest.mark.real_api.
    raise SystemExit("Smoke test stub — implement OpenRouterClient.complete first.")
