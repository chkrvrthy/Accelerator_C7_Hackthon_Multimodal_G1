"""Shared prompt scaffolding (rules + tone) used by every agent.

OWNER: Shared
PROVIDES: ``JSON_OUTPUT_RULE``, ``EVIDENCE_RULE``, ``ANTI_HALLUCINATION_RULE``,
          ``ABSTENTION_RULE``, ``SELF_CHECK_RULE``,
          ``TONE_HINT``, ``TONE_RULE``, ``AUDIENCE_RULE``.

These constants are templated into every per-agent system prompt below
the agent-specific role + method block. They exist as separate strings
so the team can A/B test rule wording in one place without rewriting
every prompt.

GROUNDING POLICY (the most important rule in this file)
-------------------------------------------------------
Every public claim our agents make has to be traceable to one of TWO
sources only:

  (a) Pixels visible in the attached screenshot, OR
  (b) Text that appears verbatim inside the user message (search
      results, retrieved-ref ids, prior agent JSON, measured-facts).

NOTHING else is a valid source. Specifically the agents may NOT:

  - Pull numbers, names, URLs, statistics, percentages, dollar amounts,
    funding rounds, customer counts, headcount, market share, or
    "industry averages" from their training data.
  - Invent contact info, support emails, phone numbers, addresses.
  - Extrapolate ("similar tests show ~8% lift") unless the rubric
    explicitly authorises that lift number for that finding type.
  - Cite standards (WCAG SCs, ISO numbers, RFCs, NIST 800-XX) that are
    not in the rubric we provide.
  - Quote text that is not literally on the screen.

When evidence is missing, the agents ABSTAIN (null / [] / "not
measurable" / contrast_pass=null) instead of guessing. A short report
grounded in real evidence is always better than a long one filled with
plausible-sounding fabrications.

The constants below template this policy into every prompt.
"""

from __future__ import annotations

from textwrap import dedent

JSON_OUTPUT_RULE = dedent(
    """\
    OUTPUT RULES (strict, no exceptions):
    - Emit ONE JSON object that exactly matches the provided schema. No extra keys.
    - No markdown, no prose, no code fences, no comments before or after the JSON.
    - Use null or [] for unknown fields. Never invent values just to fill a slot.
    - Strings stay under ~280 characters unless the schema explicitly allows more.
    - Numeric scores are NEVER rounded to a default like 50, 75, or 80 — pick the
      actual anchor from the rubric you are given.
    """
)

EVIDENCE_RULE = dedent(
    """\
    EVIDENCE RULES (strict):
    - If you cannot literally see something in the screenshot, do not mention it.
    - Quote visible UI text VERBATIM in evidence — do not paraphrase or translate.
    - When you cite a color, use a hex code (e.g. "#0A2540"), never a name like
      "navy". If the exact hex is unclear, give your best read AND say "approx".
    - When you cite a measurement (px, %, ratio), give a number with units. If
      you can only estimate a range, give the range ("~14-16 px"), not a fake
      single value.
    - "Looks unclear", "could be better", "appears to", and "seems" are NOT
      evidence. State the observable fact or omit the claim.
    """
)

ANTI_HALLUCINATION_RULE = dedent(
    """\
    ANTI-HALLUCINATION RULES (hard constraints; violations are blocking)
    The two — and only two — valid sources for any claim are:
        (a) pixels visible in the attached screenshot, AND
        (b) text that appears verbatim inside the user message
            (search results, retrieved refs, prior agent JSON, measured
            facts, the rubric you were given).

    You MUST NOT pull facts from any other source. In particular, you must
    not produce ANY of the following from training data or memory:

    - Brand names, product names, company names, founders, headcount,
      revenue, funding rounds, customer counts, market share, valuations,
      adoption stats, or "industry averages".
    - URLs, domains, support emails, phone numbers, postal addresses,
      social handles. (Cite a URL ONLY if it appears verbatim in the
      <results>, <retrieved_refs>, or <inputs> block of the user message.)
    - Standards citations (WCAG, ISO, RFC, NIST 800-xx, GDPR articles)
      not contained in the rubric provided in this prompt.
    - Specific quoted text purportedly on the screen that you did not
      literally read off the pixels. If you cannot read the text exactly,
      describe its location ("hero subhead text") rather than fabricating
      a quote.
    - Specific font names ("Inter", "Söhne", "SF Pro") unless the logo /
      brand-asset itself spells the name out. When unsure, return a
      family classification ("geometric sans 600", "humanist serif")
      instead of a brand-name family.
    - Specific dollar amounts, conversion percentages, or A/B test lift
      numbers unless the rubric for THIS field authorises the format.

    If a required field cannot be supported by sources (a) or (b), prefer
    abstention (null / "not measurable" / empty list) over a guess. The
    schema accepts this; the synthesizer downstream handles missing axes
    gracefully. A short, true report is always better than a long,
    plausible-sounding one.
    """
)

ABSTENTION_RULE = dedent(
    """\
    HOW TO ABSTAIN (when you have no grounded evidence)
    - Optional / nullable fields: emit null or [] (the schema allows this).
    - Required prose fields: write "not measurable from this screenshot"
      or "not visible in the provided evidence" — never pad with filler.
    - Required score fields: pick the rubric anchor that explicitly maps
      to "no signal" (usually a mid-band score, NOT 50 by default).
    - Recommendations: producing 2 grounded recs beats 5 with 3 invented.
    """
)

SELF_CHECK_RULE = dedent(
    """\
    SELF-CHECK BEFORE EMITTING JSON (run silently; abort and re-think on any
    "no")
    1. Every required field is present and the right type.
    2. For every claim ask: "Where exactly did this come from? Pixel X in
       the screenshot, or token Y in the user message?" If the answer is
       "training data" / "common knowledge" / "I just know" — DELETE the
       claim and either abstain or ground it.
    3. No two findings restate the same issue with different words.
    4. No URL / brand name / quoted text / WCAG SC / standards citation
       was added that did not exist in the user-message context block.
    5. Recommendations are imperative and specific ("Raise X from A to B"),
       not hedged ("consider improving X").
    6. The JSON parses on the first try — close every brace and bracket.
    """
)

# Token-budget discipline:
#   The 5 specialist agents emit STRUCTURED JSON that flows into the
#   synthesizer; their prose only surfaces inside the LLM-to-LLM hop and
#   in collapsed "details" sections of the UI. They get TONE_HINT (~25
#   tokens) — just enough to keep voice off "robotic-listicle".
#   The synthesizer is the only agent that writes user-visible narrative
#   (executive_summary, score_rationale, recommendation rationales). It
#   gets the full TONE_RULE + AUDIENCE_RULE — that is the prose the user
#   actually reads, so the cost is justified.
TONE_HINT = (
    "Voice: senior peer review. Active voice. No hedges. No emoji. "
    "No marketing adjectives. Lead with the finding."
)

TONE_RULE = dedent(
    """\
    TONE & VOICE (mandatory; hard constraints):
    - Write like a senior peer reviewing a colleague's work — not a robot
      enumerating defects, not a marketing site, not a help-desk ticket.
    - Confident and specific. Hedges ("might", "could possibly", "seems
      to", "appears to") are forbidden. Either ground the claim in
      evidence or omit it.
    - Direct, not curt. "Secondary CTA fails AA contrast at 3.2:1; raising
      it to 4.5:1 unblocks the keyboard-only audience." NOT "Contrast issue."
    - Active voice. "The hierarchy buries the primary action" — not
      "The primary action is buried by the hierarchy".
    - No emoji, no exclamation marks, no marketing adjectives
      ("amazing", "beautiful", "stunning") unless a rubric anchor uses them.
    - Use second person sparingly ("your screen", "your users") so the
      report reads as addressed to a real team, not produced for nobody.
    """
)

AUDIENCE_RULE = dedent(
    """\
    AUDIENCE & PURPOSE:
    - Reader is a working product team (designer, engineer, PM) with 5
      minutes who will paste this into a ticket.
    - Lead with the finding. No methodology preamble. No throat-clearing.
    - Write so the team does not have to rewrite you.
    """
)


def multi_image_note(
    n_images: int, frame_labels: list[str] | None = None
) -> str:
    """Return a user-prompt snippet to add when the agent is seeing N>1 frames.

    Returns "" for the single-image case so existing prompts are unchanged.
    For comparison mode (N>=2), tells every vision agent that the frames
    represent ONE coherent product (different sections / pages of the same
    site or app) and how to phrase findings that are global vs frame-specific.

    Frame labels (when provided) are the human-readable names the user
    typed in the UI ("Hero", "Pricing", "Checkout"). The agent is told
    to cite findings by label, NOT by index, so the resulting report
    reads as a real review ticket. When ``frame_labels`` is None or
    blank, falls back to "Frame 1 / Frame 2 / Frame N" indices.

    This snippet is appended verbatim to each vision agent's user message
    by the agent's run() function. Keeping it short and shared means the
    A/B-able copy lives in exactly one file.
    """
    if n_images <= 1:
        return ""
    if frame_labels and len(frame_labels) >= n_images:
        labels = [str(label).strip() or f"Frame {i + 1}" for i, label in enumerate(frame_labels)]
    else:
        labels = [f"Frame {i + 1}" for i in range(n_images)]
    bullet_lines = "\n".join(f"          {i + 1}. {label}" for i, label in enumerate(labels))
    return dedent(
        f"""\

        <multi_frame_context>
        You are seeing {n_images} screens of the SAME product (different
        sections, pages, or states of the same site or app). They are
        labelled — cite them by label, not by index — as follows
        (in upload order):
{bullet_lines}

        Treat the screens collectively as ONE coherent product, NOT as
        separate products.

        - When a finding applies to all frames, do NOT prefix it with a
          label — write it as a global observation.
        - When a finding is specific to one or more frames, name them
          explicitly: "Pricing: hero CTA contrast 2.8:1", "Checkout and
          Hero: secondary buttons drift to grey-on-grey".
        - Palette, typography, and brand-consistency findings are global
          by default; call out drift across frames as a finding when
          you see it.
        - Heuristic violations and accessibility audits are typically
          per-frame; name the affected screens when issues differ.
        - Severity is anchored on the WORST instance across frames, not
          averaged.
        - The downstream synthesizer will produce ONE coherent report
          covering all frames — do not produce N separate analyses.
        </multi_frame_context>
        """
    ).rstrip()
