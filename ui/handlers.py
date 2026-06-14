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
    frame_labels_text: str = "",
) -> Generator[tuple[str, dict[str, Any], dict[str, Any] | None], None, None]:
    """Streaming run handler for Tab 1.

    The runtime mode (real APIs vs offline fakes) is read from ``.env`` —
    specifically ``USE_REAL`` and the presence of ``OPENROUTER_API_KEY``.
    There is no UI override; the Settings tab shows what's loaded.

    MULTI-IMAGE
    -----------
    ``image`` is whatever ``gr.File(file_count="multiple")`` hands us —
    a single path, a list of paths, or a list of file-like objects.
    The handler normalizes that into a list of paths and runs the entire
    batch through ``preflight_batch`` before any tokens are spent. Every
    vision agent then sees all N frames in one call so the resulting
    report compares them as a single coherent product.

    ``frame_labels_text`` is a newline-separated list of labels typed by
    the user (one per frame, in upload order). Blank or shorter input
    falls back to the filename stem so every frame always has a name
    the synthesizer can cite by.

    GRACEFUL ERROR HANDLING
    -----------------------
    Every exception that escapes this function would land in Gradio's
    raw error dialog with a Python traceback. That is hostile to users
    and leaks stack-frame paths from the server. We instead:

      1. Validate the upload(s) via ``preflight_batch`` -> ``UploadError``
         with a user-friendly title + body.
      2. Wrap the rest of the run in a broad ``except Exception``,
         log the full traceback server-side, and yield a clean banner.
    """
    raw_paths = _normalize_uploads(image)
    if not raw_paths:
        yield (
            _status_message(
                "Upload needed",
                "Add at least one PNG or JPG screenshot first.",
            ),
            {},
            None,
        )
        return

    # SAFETY GATE: validate the BATCH (size + per-file shape) BEFORE we
    # spend tokens or boot the agent graph. preflight_batch converts
    # every failure into an UploadError carrying user-readable copy.
    try:
        from src.utils.safe_image import (
            UploadError,
            downsize_for_pipeline,
            preflight_batch,
        )

        preflight_batch(raw_paths)
        # Pre-resize each frame before the pipeline ever sees it. The
        # originals are left intact; the pipeline reads the downsized
        # copies. Multi-frame runs amortize this once per upload.
        image_paths = [downsize_for_pipeline(p) for p in raw_paths]
    except UploadError as e:
        log.warning(
            "on_run: rejected upload(s) %s — %s",
            [p.name for p in raw_paths],
            e.debug_detail,
        )
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

        n = len(image_paths)
        labels = _resolve_frame_labels(frame_labels_text, image_paths)

        # SESSION MARKER. The on-disk app log is rolling (10 MB rotation)
        # and shared across all runs in a process. Without an explicit
        # boundary, grepping the file for "this morning's broken run"
        # is painful. We write a single highly-greppable line at start
        # and end of every run so users can do:
        #     grep -n "RUN START" data/logs/app.log
        # to slice the log by run, then use the sandwiched lines as the
        # context for that one analysis. The session id is a short uuid
        # so it can be cited in a bug report without leaking PII.
        import uuid as _uuid

        session_id = _uuid.uuid4().hex[:8]
        log.info(
            "RUN START session=%s frames=%d mode=%s labels=%s",
            session_id,
            n,
            "real" if use_real else "fake",
            ",".join(labels),
        )

        if n == 1:
            running_detail = f"Reviewing {labels[0]} with {mode_label}."
        else:
            running_detail = (
                f"Reviewing {n} frames as one product with {mode_label}: "
                f"{', '.join(labels)}."
            )
        yield (
            _status_message("Analysis running", running_detail),
            {},
            None,
        )
        report: DesignReport = run_graph(
            image_paths,
            instructions=instructions or None,
            frame_labels=labels,
            deps=deps,
        )
        report_dict = report.model_dump()

        cost = get_cost_tracker().snapshot()
        frames_label = "frame" if n == 1 else "frames"
        detail = (
            f"Score: {report.overall_score:.1f}/100 across {n} {frames_label}. "
            f"Tokens used: {cost['total_tokens']:,} "
            f"(~${cost['estimated_usd']:.4f}); cache hits: {cost['cache_hits']}. "
            "Open Report."
        )
        yield (
            _status_message("Report ready", detail),
            report_dict,
            report_dict,
        )
        log.info(
            "RUN END session=%s run_id=%s score=%.1f tokens=%d usd=%.4f",
            session_id,
            report.run_id,
            report.overall_score,
            cost["total_tokens"],
            cost["estimated_usd"],
        )
    except Exception as e:
        log.exception("on_run: unexpected failure during analysis")
        # Best-effort end marker so a failed run still has a clear
        # boundary in the log. ``session_id`` may not be defined if the
        # failure was during deps construction; guard it.
        try:
            log.warning(
                "RUN END session=%s status=failed error=%s",
                locals().get("session_id", "unknown"),
                type(e).__name__,
            )
        except Exception:
            pass
        title, body = _classify_run_error(e)
        yield (_status_message(title, body), {}, None)


def _resolve_frame_labels(text: str, image_paths: list[Path]) -> list[str]:
    """Parse the free-form labels textbox into one label per frame.

    The user types one label per line in the UI (in upload order). We:
      - Split on newlines, trim whitespace, drop blanks.
      - Pad with the filename stem of each remaining frame so the result
        is ALWAYS the same length as image_paths.
      - Truncate any extras (a label without a frame is silently ignored).

    Single-frame runs return ``[label]`` so the running-status text
    always has something nicer than the temp filename to display.
    """
    typed = [line.strip() for line in (text or "").splitlines() if line.strip()]
    out: list[str] = []
    for i, p in enumerate(image_paths):
        if i < len(typed):
            out.append(typed[i])
        else:
            out.append(p.stem or f"Frame {i + 1}")
    return out


def _normalize_uploads(image: Any) -> list[Path]:
    """Coerce the gr.File payload into a list of Paths.

    With ``file_count="multiple"`` Gradio hands us a list of strings (when
    type="filepath"); legacy single-file calls hand us a single string or
    a single file-like object. We accept all three shapes so the rest of
    the handler never branches on payload type. Drops empties / None
    entries silently.
    """
    if image is None:
        return []
    if isinstance(image, (str, Path)):
        return [Path(image)]
    items = list(image) if isinstance(image, (list, tuple)) else [image]
    out: list[Path] = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, (str, Path)):
            out.append(Path(it))
        else:
            name = getattr(it, "name", None)
            if name:
                out.append(Path(name))
    return out


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

