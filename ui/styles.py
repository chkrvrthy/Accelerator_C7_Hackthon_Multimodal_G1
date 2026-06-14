"""Gradio app static assets — wraps CSS / JS / HEAD HTML.

OWNER: Person E
USED BY: ui/app.py.

The CSS bulk lives in a real CSS file (``ui/static/app.css``) so editors
and linters can treat it as CSS, not as a 1.3k-line Python string. The
small JS + HTML head fragments stay inline because they are tiny and
because Gradio expects them as Python strings.

PUBLIC NAMES
------------
- ``APP_CSS`` — string content of ``ui/static/app.css`` (loaded once).
- ``FORCE_LIGHT_THEME_JS`` — JS run on app load to pin light theme.
- ``FORCE_LIGHT_THEME_HEAD`` — HTML appended to the document <head>.
"""

from __future__ import annotations

from pathlib import Path

# Read once at import time. Cheap; the CSS is ~30 KB and loading it on
# every Gradio request would add latency for zero benefit.
_CSS_PATH = Path(__file__).resolve().parent / "static" / "app.css"
APP_CSS: str = _CSS_PATH.read_text(encoding="utf-8")

FORCE_LIGHT_THEME_JS: str = """
() => {
  const root = document.documentElement;
  root.classList.remove("dark");
  root.classList.add("light");
  root.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");

  const params = new URLSearchParams(window.location.search);
  if (params.get("__theme") !== "light") {
    params.set("__theme", "light");
    const nextUrl = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }

  return [];
}
"""

FORCE_LIGHT_THEME_HEAD: str = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script>
  document.documentElement.classList.remove("dark");
  document.documentElement.classList.add("light");
  document.documentElement.dataset.theme = "light";
  localStorage.setItem("theme", "light");
  localStorage.setItem("__theme", "light");
  localStorage.setItem("gradio-theme", "light");
</script>
"""
