"""Static HTML / markdown copy for the Gradio UI.

OWNER: Person E
USED BY: ui/app.py — every tab embeds blocks from this module.

WHY THIS FILE EXISTS
--------------------
Every guide card, hero band, and limit explainer used to live as a
multi-line string inside ``ui/app.py``. Extracting them keeps app.py
focused on *what hooks into what* (callbacks, layout) and lets a
non-engineer (designer, PM) tweak wording without touching wiring code.

DESIGN CONSTRAINTS (June 2026 v2)
---------------------------------
The first revision packed every limit, expectation, and rule onto the
page. Result: the panel was a wall of muted-grey text with no clear
hierarchy and the user could not see which controls were primary.
This revision flips the default:

- Long-form explanations live in **collapsed `<details>` panels**
  with a tiny info-icon (``i``) summary — visible on demand only.
- Single-line `info=` strings on Gradio fields render as the
  framework's own hover tooltip and are deliberately short (one
  sentence, max ~100 chars).
- Section headers carry their explanation inline as a terse
  one-liner; only the "(why?)" toggle exposes the rationale.
- No more 6-bullet markdown blocks under controls. The right place
  for that copy is README + the FAQ, not the form.

CONVENTION
----------
- Static HTML/markdown: ``UPPER_SNAKE`` constants.
- Runtime-derived HTML: functions returning strings.
- Always close ``<details>`` so the panel starts collapsed.
- Field ``info=`` strings go straight into the Gradio API; no HTML.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

# Project root used to convert absolute paths into anonymous,
# repo-relative strings before they are rendered in the UI. The
# absolute path on a contributor's machine can leak the username
# and company filesystem layout (e.g. ``/u/<name>/<corp-share>/...``);
# we never want that visible in screenshots, demos, or recordings.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _display_path(p: Any) -> str:
    """Return a privacy-safe, repo-relative version of ``p`` for the UI.

    - Inside the repo  → ``data/reports``                  (relative)
    - Outside the repo → ``<parent-name>/<basename>``      (basenamed)
    - Empty / unset    → ``"(unset)"``

    No absolute path is ever returned. This is the single hop every
    user-visible path string in the Settings card / log surface goes
    through.
    """
    if p is None or p == "":
        return "(unset)"
    path = Path(str(p)).expanduser()
    try:
        rel = path.resolve().relative_to(_PROJECT_ROOT)
        return str(rel) if str(rel) else "."
    except (ValueError, OSError):
        # Outside the repo (CI scratch dir, /tmp, network mount).
        # Drop the leading prefix and keep just the last two segments —
        # enough to be informative without revealing the user's home.
        parts = path.parts
        if len(parts) >= 2:
            return str(Path(*parts[-2:]))
        return path.name or "(unset)"


def _log_file_display() -> str:
    """Return the display-safe path of the active log file (or 'disabled').

    Wraps ``src.utils.logger.get_log_file`` so the Settings tab can
    render the path without importing logger internals. We swallow any
    import-time errors (the logger module loads ``src.config``, which
    is already loaded by the time we render Settings, but be paranoid)
    and degrade to ``"(disabled)"``.
    """
    try:
        from src.utils.logger import get_log_file

        path = get_log_file()
    except Exception:
        return "(disabled)"
    if path is None:
        return "(disabled)"
    return _display_path(path)

# --- Hero ----------------------------------------------------------- #

HERO_BAND_HTML = """
<section class="hero-band">
  <span class="eyebrow">Multimodal review</span>
  <h1>Design Analysis Suite</h1>
  <p>
    Upload a screen for a fast visual, UX, accessibility, brand, and market review.
    Five specialist agents critique in parallel and ship a single prioritized report.
  </p>
  <div class="chip-row">
    <span class="chip">Visual</span>
    <span class="chip">UX</span>
    <span class="chip">Accessibility</span>
    <span class="chip">Brand</span>
    <span class="chip">Market</span>
  </div>
</section>
"""

# Compact 3-step strip — one line each, no body copy.
STEPS_EXPLAINER_HTML = """
<div class="steps">
  <div class="step accent-teal"  data-step="1"><b>Upload 1&ndash;5 screens</b></div>
  <div class="step accent-coral" data-step="2"><b>Add labels &amp; context</b></div>
  <div class="step accent-gold"  data-step="3"><b>Run &amp; review</b></div>
</div>
"""

# --- Analyze tab: collapsible "?" disclosure ----------------------- #
# Replaces the old 6-bullet markdown block + 3-card right rail.
# The terse summary line ("What to upload") is always visible; the
# detailed expectations live behind a click so they don't drown the
# form. Single source of truth for "first-time" guidance.

ANALYZE_HELP_HTML = """
<details class="ui-help">
  <summary><span class="info-glyph">i</span> What to upload &mdash; tap to expand</summary>
  <div class="ui-help-body">
    <div class="ui-help-grid">
      <div class="ui-help-col accent-teal">
        <h4>Do upload</h4>
        <ul>
          <li>1&ndash;5 full-screen captures of <b>the same product</b></li>
          <li>Distinct screens (Hero, Pricing, Dashboard) in flow order</li>
          <li>1024&nbsp;px+ wide; PNG/JPG/WebP &le; 20&nbsp;MB</li>
        </ul>
      </div>
      <div class="ui-help-col accent-coral">
        <h4>Don't upload</h4>
        <ul>
          <li>Phone photos, blurry or angled shots</li>
          <li>Crops of one button or section</li>
          <li>Screens from different products mixed together</li>
          <li>PDFs, video, GIFs, code, live URLs, real PII</li>
        </ul>
      </div>
      <div class="ui-help-col accent-gold">
        <h4>What you'll get</h4>
        <ul>
          <li>Overall score 0&ndash;100 with a paragraph WHY</li>
          <li>Per-axis breakdown + per-frame heatmap (multi-frame)</li>
          <li>Ranked fixes with the agent that flagged each one</li>
          <li>Brand RAG references on the References tab</li>
        </ul>
      </div>
    </div>
  </div>
</details>
"""

# --- Field-level tooltips (Gradio info=...) ------------------------- #
# Each is one short sentence — Gradio renders these as a hover tooltip
# under the field label. Long-form rationale stays in ANALYZE_HELP_HTML.

FRAME_LABELS_INFO = (
    "Optional. One label per line in upload order. Tip: rename your "
    "files first and skip this — filename becomes the label."
)

CONTEXT_FIELD_PLACEHOLDER = (
    "audience: enterprise IT buyers in EMEA; "
    "brand: trustworthy, technical, no jargon; "
    "goal: book demos from the pricing page"
)

CONTEXT_FIELD_INFO = (
    "Tells every agent who this is FOR and what 'good' looks like. "
    "Skipping it gives generic feedback."
)

REFERENCES_SEARCH_INFO = (
    "Plain English works. Stripe, Linear, Notion. Returns top 8 visual matches."
)

# Empty-state body shown in the log card before the first run.
EMPTY_LOG_BODY = (
    "Drop 1–5 screenshots of the same product, then press Run. "
    "Real-API runs take 60–120 s; offline runs are instant."
)

# Tiny note shown beneath the Run button.
RUN_BUTTON_TIP_MARKDOWN = (
    "_Press once and wait. Offline: 30–90 s, free. "
    "Real-API: 60–120 s, ≈ $0.05 per run. Same image again = cached, free._"
)

# --- References tab ------------------------------------------------- #

REFERENCES_INTRO_HTML = """
<div class="ui-section-intro">
  <h2>References</h2>
  <p>What the <b>Brand</b> and <b>Market</b> agents looked at.
  Auto-fills after every run; the search below is for digging deeper.</p>
  <details class="ui-help inline">
    <summary><span class="info-glyph">i</span> What is this tab?</summary>
    <div class="ui-help-body">
      <p>Two sections.</p>
      <ul>
        <li><b>Top:</b> brand RAG hits + market URLs from the most recent
        run. Auto-populates &mdash; no second click needed.</li>
        <li><b>Bottom:</b> ad-hoc search across the local CLIP index and
        the live web. Use it when you want sources beyond the
        agents' picks.</li>
      </ul>
      <p><b>Empty?</b> Run an analysis from the <b>Analyze</b> tab first.</p>
    </div>
  </details>
</div>
"""

REFERENCES_RUN_EMPTY_HTML = """
<div class="reference-card">
  <p>Run an analysis from the <b>Analyze</b> tab. Brand and market
  references will appear here automatically.</p>
</div>
"""

REFERENCES_SEARCH_HEADER_HTML = """
<h3 class="ui-subhead">Search for more references</h3>
"""

REFERENCES_SEARCH_EMPTY_HTML = """
<div class="reference-card">
  <p>Type a pattern or product category and press Search.</p>
</div>
"""

# --- Settings tab --------------------------------------------------- #

SETTINGS_INTRO_HTML = """
<div class="ui-section-intro">
  <h2>Settings</h2>
  <p>Read-only diagnostics. To change anything, edit
  <code>.env</code> (most knobs) or <code>src/config.py</code>
  (model defaults) then restart.</p>
  <details class="ui-help inline">
    <summary><span class="info-glyph">i</span> Why no toggles?</summary>
    <div class="ui-help-body">
      <p>The app is built for <b>reproducible demos</b>: every run uses
      the same configuration so the report you ship is the report your
      reviewer sees. UI controls would let a teammate flip a switch
      mid-demo. Source labels show where each value lives:</p>
      <ul>
        <li><span class="src-badge env">.env</span> &mdash; project
        <code>.env</code> file. Edit, save, restart.</li>
        <li><span class="src-badge code">code</span> &mdash;
        <code>src/config.py</code> for model defaults. Advanced.</li>
        <li><span class="src-badge auto">auto</span> &mdash; computed
        from the filesystem; not user-editable.</li>
      </ul>
      <p><b>Switch to real APIs:</b> add <code>OPENROUTER_API_KEY=&hellip;</code>
      and <code>USE_REAL=1</code> in <code>.env</code>, restart. Cost
      ≈ $0.05 / run on default models.</p>
    </div>
  </details>
</div>
"""

# Subheads in the Settings tab — short, no body copy. Long detail
# moved into the <details> in SETTINGS_INTRO_HTML above.
COST_TELEMETRY_HEADER_HTML = (
    '<h3 class="ui-subhead">Cost &amp; token telemetry</h3>'
    '<p class="ui-subhead-note">Running totals for this app process; '
    "resets when you restart.</p>"
)

TOOL_REGISTRY_HEADER_HTML = (
    '<h3 class="ui-subhead">Tool registry</h3>'
    '<p class="ui-subhead-note">Every <code>@tool</code> wired into the '
    "agent graph. Auditable; registered at boot in "
    "<code>src/agents/tools.py</code>.</p>"
)


def runtime_config_card_html(
    cfg: Any,
    *,
    has_openrouter_key: bool,
    cache_file_count: int,
    local_reference_file_count: int,
    vector_row_count: int,
) -> str:
    """Render the read-only configuration card with source badges.

    Every line carries one of three source badges so the user knows
    where to actually go to change a value:
      - .env  → edit the project's .env file and restart
      - code  → edit src/config.py and restart (advanced)
      - auto  → computed at boot from disk; not user-editable

    The card is intentionally NOT a form. UI controls would let a
    reviewer flip a switch mid-demo, breaking reproducibility.
    """
    return f"""
<div class="settings-card">
  <h3>Current configuration <span class="settings-readonly-tag">read-only</span></h3>
  <p><b>OPENROUTER_API_KEY loaded</b>: {has_openrouter_key}
     <span class="src-badge env">.env</span></p>
  <p><b>USE_REAL</b>: {cfg.use_real}
     <span class="src-badge env">.env</span>
     <i>controls offline fakes vs real APIs</i></p>
  <p><b>TAVILY_API_KEY loaded</b>: {bool(cfg.tavily_api_key)}
     <span class="src-badge env">.env</span>
     <i>optional; enables live-web market signals</i></p>
  <p><b>Text model</b>:
     <code>{html.escape(cfg.default_text_model)}</code>
     <span class="src-badge code">code</span></p>
  <p><b>Vision model</b>:
     <code>{html.escape(cfg.default_vision_model)}</code>
     <span class="src-badge code">code</span></p>
  <p><b>Temperature</b>: {cfg.default_temperature}
     <span class="src-badge code">code</span>
     <i>kept low for consistent structured output</i></p>
  <p><b>Max tokens / call</b>: {cfg.default_max_tokens:,}
     <span class="src-badge code">code</span>
     <i>caps the per-call cost predictably</i></p>
  <p><b>Cache</b>: {"DISABLED" if cfg.cache_disabled else "enabled"}
     ({cache_file_count} cached responses)
     <span class="src-badge auto">auto</span>
     <i>re-runs of the same image+prompt are instant + free</i></p>
  <p><b>Local reference images</b>: {local_reference_file_count}
     <span class="src-badge auto">auto</span>
     <i>brand RAG corpus on disk</i></p>
  <p><b>Indexed reference rows</b>: {vector_row_count}
     <span class="src-badge auto">auto</span>
     <i>CLIP embeddings in LanceDB &mdash; what the brand agent searches</i></p>
  <p><b>Reports directory</b>:
     <code>{html.escape(_display_path(cfg.report_dir))}</code>
     <span class="src-badge auto">auto</span>
     <i>repo-relative; each run drops a JSON report here</i></p>
  <p><b>App log file</b>:
     <code>{html.escape(_log_file_display())}</code>
     <span class="src-badge auto">auto</span>
     <i>every run also writes here &mdash; tail this file instead of the
     console (10 MB rotation, keeps 5 backups). Set
     <code>LOG_TO_FILE=0</code> in .env to disable.</i></p>
</div>
"""
