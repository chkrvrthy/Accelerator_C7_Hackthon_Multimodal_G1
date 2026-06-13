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

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from src.config import Settings, settings
from src.utils.logger import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

log = get_logger(__name__)


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
            ValueError: when the model returns malformed JSON.
            openai.OpenAIError: on transport / auth / rate-limit failures.
        """
        # HINT: the call sequence is exactly five steps. Resist adding more.
        #   1. ``messages = [{"role":"system","content":system}, {"role":"user","content":user}]``
        #   2. ``rf = self._schema_payload(schema)`` (helper below)
        #   3. ``resp = self._client().chat.completions.create(model=..., messages=messages,``
        #      ``response_format=rf, temperature=temperature or self.settings.default_temperature,``
        #      ``max_tokens=self.settings.default_max_tokens)``
        #   4. ``raw = resp.choices[0].message.content``  (always a JSON string in this mode)
        #   5. ``return schema.model_validate_json(raw)``
        #
        # HINT: wrap step 3 with ``cost.cached`` once cost.py is real:
        #     return _cached_complete(system=..., user=..., schema=..., model=...)
        # The cache key is built from your inputs; do NOT include trace ids.
        #
        # HINT: rate-limit handling — only on RateLimitError, not on every
        # OpenAIError:
        #     for attempt in range(3):
        #         try: return ...
        #         except openai.RateLimitError:
        #             time.sleep(1.5 ** attempt + random.random() * 0.2)
        #     raise  # exhausted retries
        #
        # HINT: when a provider rejects ``json_schema`` (rare but real), retry
        # ONCE with ``response_format={"type":"json_object"}`` and pass a
        # textual schema description in the system prompt. Catch
        # ``openai.BadRequestError`` and inspect ``e.body["error"]["message"]``.
        # TODO(person-a): wire steps 1–5 above. ~25 lines.
        raise NotImplementedError("Person A: implement OpenRouterClient.complete")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _client(self) -> OpenAI:
        """Lazy-construct the OpenAI SDK with OpenRouter base URL + headers.

        HINT: lazy so importing this module is cheap even when no key is set.
        Other slices (Person B, C, D) load this file just to type-check —
        a non-lazy SDK construction would force them to install ``openai``.
        """
        # TODO(person-a): one-liner build, cached on self._sdk:
        #   from openai import OpenAI
        #   if self._sdk is None:
        #       self._sdk = OpenAI(
        #           api_key=self.settings.openrouter_api_key,
        #           base_url=self.settings.openrouter_base_url,
        #           default_headers={
        #               "HTTP-Referer": self.settings.openrouter_site_url,
        #               "X-Title": self.settings.openrouter_app_name,
        #           },
        #       )
        #   return self._sdk
        #
        # HINT: missing ``OPENROUTER_API_KEY`` should raise a clear error here,
        # not deep inside the SDK at first call:
        #     if not self.settings.openrouter_api_key:
        #         raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
        raise NotImplementedError

    @staticmethod
    def _schema_payload(schema: type[BaseModel]) -> dict[str, Any]:
        """Build the OpenRouter ``response_format`` payload for a Pydantic model.

        Returns the dict you pass as ``response_format=...`` to the SDK.
        """
        # HINT: the OpenRouter spec accepts the following shape:
        #   {
        #       "type": "json_schema",
        #       "json_schema": {
        #           "name": schema.__name__,
        #           "schema": schema.model_json_schema(),
        #           "strict": True,
        #       },
        #   }
        # ``strict: True`` makes the model emit *only* JSON; without it the
        # model occasionally adds prose that breaks model_validate_json.
        #
        # LOGIC: pydantic v2's ``model_json_schema()`` already produces a
        # JSON-Schema-compliant dict — no transformation needed.
        # TODO(person-a): build and return the dict.
        raise NotImplementedError


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
