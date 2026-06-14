"""Editorial fallback references for the References tab.

OWNER: Person A
SPRINT CONCEPTS: Sprint 3 (RAG, retrieval), Sprint 6 (graceful degradation).

WHY THIS FILE EXISTS
--------------------
The References tab has three data sources, in order of preference:

  1. LanceDB image-index search (CLIP embeddings)         -- best
  2. Tavily / DuckDuckGo web search                       -- okay
  3. The editorial list below                             -- always works

Without the third source the tab would be empty in the offline demo
environment (no API keys, empty index). For a hackathon demo / new
user that's the worst possible first impression: the feature looks
broken.

The list below is a hand-curated set of well-known, source-of-truth
design references with stable URLs. We pick from it by simple keyword
match on the query — no LLM, no network, no tokens spent. It is by
design *not* the best possible answer; it is the always-available one.

Update process:
    Add new entries to ``_EDITORIAL_REFS`` when you find a reference
    you keep typing into demo presentations. Keep it < 30 entries —
    longer and the keyword match becomes noisy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EditorialRef:
    """One curated reference."""

    title: str
    url: str
    why: str
    keywords: tuple[str, ...]


_EDITORIAL_REFS: tuple[EditorialRef, ...] = (
    # --- Accessibility ---------------------------------------------------
    EditorialRef(
        title="WCAG 2.2 — Web Content Accessibility Guidelines",
        url="https://www.w3.org/WAI/WCAG22/quickref/",
        why="Source of truth for contrast, focus, target size, and "
        "every accessibility recommendation the agent makes.",
        keywords=(
            "accessibility",
            "wcag",
            "contrast",
            "focus",
            "screen reader",
            "a11y",
        ),
    ),
    EditorialRef(
        title="WebAIM Contrast Checker",
        url="https://webaim.org/resources/contrastchecker/",
        why="Practical contrast verifier used by every accessibility "
        "team. Pairs with the agent's contrast_pass measurement.",
        keywords=("contrast", "color", "accessibility", "ratio"),
    ),
    # --- UX heuristics ---------------------------------------------------
    EditorialRef(
        title="Nielsen Norman — 10 Usability Heuristics",
        url="https://www.nngroup.com/articles/ten-usability-heuristics/",
        why="The 10 heuristics the UX agent cites in every critique.",
        keywords=("ux", "heuristic", "nielsen", "usability"),
    ),
    EditorialRef(
        title="Refactoring UI — Visual hierarchy chapter (free preview)",
        url="https://www.refactoringui.com/",
        why="Concrete fixes for the visual issues the agent flags "
        "(hierarchy, weight, contrast, breathing room).",
        keywords=("visual", "hierarchy", "typography", "ui", "design"),
    ),
    EditorialRef(
        title="Baymard — Checkout & form research",
        url="https://baymard.com/research",
        why="Empirical benchmarks for checkout, payments, forms — what "
        "the market agent leans on for fintech / commerce screens.",
        keywords=("checkout", "form", "payment", "ecommerce", "commerce", "stripe"),
    ),
    # --- Design systems --------------------------------------------------
    EditorialRef(
        title="Material Design 3",
        url="https://m3.material.io/",
        why="Mature reference for components, motion, spacing tokens. "
        "Useful when the brand agent has nothing to compare against.",
        keywords=("material", "design system", "tokens", "components", "android"),
    ),
    EditorialRef(
        title="Apple Human Interface Guidelines",
        url="https://developer.apple.com/design/human-interface-guidelines/",
        why="iOS / macOS UX expectations the brand and UX agents cite.",
        keywords=("apple", "ios", "hig", "macos", "iphone"),
    ),
    EditorialRef(
        title="IBM Carbon Design System",
        url="https://carbondesignsystem.com/",
        why="Enterprise-grade open design system; strong on data-dense "
        "screens like dashboards, banking portals, fintech.",
        keywords=("carbon", "ibm", "enterprise", "dashboard", "fintech", "banking"),
    ),
    # --- Brand & visual --------------------------------------------------
    EditorialRef(
        title="Stripe — Brand & website examples",
        url="https://stripe.com/",
        why="Modern fintech brand benchmark — typography, color, motion, "
        "and CTA hierarchy at production scale.",
        keywords=("stripe", "fintech", "payment", "saas", "checkout"),
    ),
    EditorialRef(
        title="Material color tools — Hue, tone, accessibility",
        url="https://m3.material.io/styles/color/system/overview",
        why="Color theory + accessible color tokens. Useful when the "
        "brand agent flags color drift.",
        keywords=("color", "palette", "tone", "brand", "accessibility"),
    ),
    # --- Performance / motion --------------------------------------------
    EditorialRef(
        title="web.dev — Core Web Vitals",
        url="https://web.dev/articles/vitals",
        why="LCP, INP, CLS thresholds. The market and UX agents cite "
        "these when judging page weight or motion.",
        keywords=("performance", "vitals", "lcp", "inp", "cls", "speed"),
    ),
)


def search_editorial(query: str, limit: int = 6) -> list[EditorialRef]:
    """Return editorial refs whose keywords intersect the query.

    Pure-Python keyword match (no LLM). Falls back to ALL refs ranked by
    title similarity when no keywords match — we never return an empty
    list because the whole point of this module is "always have something
    to show".

    Args:
        query: The user's reference search string. Empty string returns
               the first ``limit`` refs (a starter set).
        limit: Max refs to return.

    Returns:
        Up to ``limit`` editorial references.
    """
    q = (query or "").lower().strip()
    if not q:
        return list(_EDITORIAL_REFS)[:limit]

    # Score by keyword hits. Each keyword that appears in the query
    # earns a point; the title also contributes (title-relevant refs
    # bubble up over weak keyword matches).
    scored: list[tuple[int, EditorialRef]] = []
    q_tokens = {t for t in q.split() if t}
    for ref in _EDITORIAL_REFS:
        kw_hits = sum(1 for kw in ref.keywords if kw in q)
        title_hits = sum(1 for tok in q_tokens if tok in ref.title.lower())
        score = kw_hits * 2 + title_hits
        if score > 0:
            scored.append((score, ref))

    if scored:
        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    # No matches: still return SOMETHING so the UI is never empty.
    return list(_EDITORIAL_REFS)[:limit]


def render_as_html(refs: list[EditorialRef]) -> str:
    """Render an EditorialRef list as a Gradio-friendly HTML block."""
    if not refs:
        return ""
    items = "".join(
        f'<li><b><a href="{r.url}" target="_blank" rel="noopener">{r.title}</a></b>'
        f' &nbsp;<span style="color:#5a6473">— {r.why}</span></li>'
        for r in refs
    )
    return (
        '<div class="reference-card" style="margin-top:14px">'
        "<h3>Editorial fallback references</h3>"
        '<p style="font-size:13px;color:#5a6473">'
        "Hand-curated sources of truth. Always available, even when the "
        "image index and web search are both unavailable."
        "</p>"
        f"<ul>{items}</ul>"
        "</div>"
    )
