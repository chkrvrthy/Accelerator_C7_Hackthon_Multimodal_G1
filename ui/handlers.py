"""Top-level event handlers wired to Gradio buttons.

OWNER: Person E
USED BY: ui/app.py.

Public surface:
  - ``on_run(image, instructions)``: streaming generator for the
    "Run analysis" button on the Analyze tab.
  - ``_classify_run_error``: maps an exception type to a user-friendly
    (title, body) banner so the UI never shows a raw Python traceback.

Behavioral guarantees:
  - Every upload is preflight-validated AND auto-resized BEFORE the
    pipeline runs (``src.utils.safe_image``). Crashes from oversized
    files cannot reach Gradio.
  - Every run is wrapped in a wide ``try/except``. Server-side, the
    full stack hits the log; client-side, a clean banner appears.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

from src.agents.base import AgentDeps, build_default_deps
from src.agents.graph import run_graph
from src.schemas.outputs import DesignReport
from src.utils.logger import get_logger
from ui.state import _default_real_mode, _fresh_settings, _has_openrouter_key, _status_message

log = get_logger(__name__)


def on_run(
    image: Any,
    instructions: str,
) -> Generator[tuple[str, dict[str, Any], dict[str, Any] | None], None, None]:
    """Streaming run handler for Tab 1.

    The runtime mode (real APIs vs offline fakes) is read from ``.env`` —
    specifically ``USE_REAL`` and the presence of ``OPENROUTER_API_KEY``.
    There is no UI override; the Settings tab shows what's loaded.

    GRACEFUL ERROR HANDLING
    -----------------------
    Every exception that escapes this function would land in Gradio's
    raw error dialog with a Python traceback. That is hostile to users
    and leaks stack-frame paths from the server. We instead:

      1. Validate the upload via ``preflight_image`` -> ``UploadError``
         with a user-friendly title + body.
      2. Wrap the rest of the run in a broad ``except Exception``,
         log the full traceback server-side, and yield a clean banner.
    """
    if image is None:
        yield (
            _status_message(
                "Upload needed",
                "Add a PNG or JPG screenshot first.",
            ),
            {},
            None,
        )
        return

    raw_path = Path(image.name if hasattr(image, "name") else image)

    # SAFETY GATE: validate the upload BEFORE we spend tokens or boot
    # the agent graph. preflight_image converts every failure into a
    # UploadError carrying user-readable copy.
    try:
        from src.utils.safe_image import (
            UploadError,
            downsize_for_pipeline,
            preflight_image,
        )

        preflight_image(raw_path)
        # Pre-resize before the pipeline ever sees the file. The original
        # is left intact; the pipeline reads the downsized copy.
        image_path = downsize_for_pipeline(raw_path)
    except UploadError as e:
        log.warning("on_run: rejected upload %s — %s", raw_path.name, e.debug_detail)
        yield (_status_message(e.user_title, e.user_body), {}, None)
        return

    _fresh_settings()
    use_real = _default_real_mode()

    if use_real and not _has_openrouter_key():
        yield (
            _status_message(
                "Missing API key",
                "USE_REAL is on but OPENROUTER_API_KEY is not set in .env. "
                "Either add the key or set USE_REAL=false in .env.",
            ),
            {},
            None,
        )
        return

    # MAIN BODY — guarded by a wide try/except so the user never sees a
    # raw traceback. Any unexpected failure shows a friendly banner and
    # the full stack lands in the server log for the operator.
    try:
        deps: AgentDeps = build_default_deps(use_real=use_real)
        mode_label = "real APIs (.env)" if use_real else "offline fakes"

        from src.llm.cost_tracker import get_cost_tracker

        get_cost_tracker().reset()

        yield (
            _status_message(
                "Analysis running",
                f"Reviewing {image_path.name} with {mode_label}.",
            ),
            {},
            None,
        )
        report: DesignReport = run_graph(
            image_path, instructions=instructions or None, deps=deps
        )
        report_dict = report.model_dump()

        cost = get_cost_tracker().snapshot()
        detail = (
            f"Score: {report.overall_score:.1f}/100. "
            f"Tokens used: {cost['total_tokens']:,} "
            f"(~${cost['estimated_usd']:.4f}); cache hits: {cost['cache_hits']}. "
            "Open Report."
        )
        yield (
            _status_message("Report ready", detail),
            report_dict,
            report_dict,
        )
    except Exception as e:
        log.exception("on_run: unexpected failure during analysis")
        title, body = _classify_run_error(e)
        yield (_status_message(title, body), {}, None)


def _classify_run_error(e: Exception) -> tuple[str, str]:
    """Map an exception type to a user-friendly (title, body) banner.

    The user never sees the exception class name or the stack frame.
    The full detail is in the server log. We classify a small number
    of common failure modes so the banner is *useful*, not just polite.
    """
    name = type(e).__name__

    # Circuit breaker open — the LLM API has been failing recently.
    if name == "CircuitOpenError":
        return (
            "API temporarily unavailable",
            "The model provider returned errors on the last few calls, so "
            "we are pausing for ~30 seconds before trying again. Try once "
            "more in a moment, or switch to offline mode (USE_REAL=false "
            "in .env) for an instant deterministic demo.",
        )

    # Provider auth / rate-limit class names from the openai SDK.
    if name in {"AuthenticationError", "PermissionDeniedError"}:
        return (
            "API key rejected",
            "The model provider rejected the API key. Open Settings to "
            "verify OPENROUTER_API_KEY is loaded, then try again.",
        )
    if name in {"RateLimitError"}:
        return (
            "Rate limit reached",
            "The model provider is rate-limiting this account. Wait a "
            "minute and try again, or switch to offline mode for a free, "
            "deterministic run.",
        )

    # Network problems.
    if name in {"APIConnectionError", "ConnectionError", "Timeout", "TimeoutError"}:
        return (
            "Could not reach the model provider",
            "There was a network problem talking to the API. Check your "
            "connection and try again. Offline mode works without any "
            "network at all.",
        )

    # Pydantic validation in case a specialist returned malformed JSON
    # and the corrective retry also failed.
    if name == "ValidationError":
        return (
            "Model returned an unexpected response",
            "The agents could not produce a clean structured report on "
            "this image. Try re-running, switch models in Settings, or "
            "use offline mode for a deterministic demo.",
        )

    # Default — useful but generic.
    return (
        "Something went wrong during analysis",
        "We have logged the details server-side and the team will look "
        "into it. Try a different screenshot, switch to offline mode "
        "(USE_REAL=false in .env), or restart the app.",
    )

