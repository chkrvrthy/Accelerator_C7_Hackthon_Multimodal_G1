# Demo Script — Multimodal AI Design Analysis Suite

> **Length:** 4 minutes target (3:30 minimum, 5:00 hard cap).
> **Speaker:** one team representative, screen-sharing the Gradio UI on
> `http://127.0.0.1:7860/`.
> **Goal:** maximize all three rubric points — Concept Score, Difficulty, Code
> Quality — in that order, because Concept Score is what we have the most of
> and what unlocks the other two.

---

## Pre-flight checklist (T-5 minutes)

1. `make ingest` — confirm reference index has rows. If empty, the References
   tab will say "No indexed matches yet" and that's a visible weakness.
2. `python ui/app.py` — wait for `Running on local URL: http://127.0.0.1:7860`.
3. Open the URL in a clean browser window. Zoom level 100%. Close DevTools.
4. Pre-stage the bundled sample: in **Analyze**, click "Try the bundled sample"
   so the file picker is already filled. Do **not** click Run yet.
5. **Decide one** — real APIs or offline fakes:
   - Real APIs: leave "Use real APIs from .env" checked. ~25 s per run, ~$0.03.
   - Offline fakes: uncheck it. Returns in <1 s. **Recommended for live demo
     unless your network and OpenRouter key are both rock solid.**
6. Keep a terminal visible with `tail -f` on a fresh log if real APIs are on,
   so judges can see the LangSmith trace IDs land.
7. Have `docs/walkthrough.html` open in a second tab as a fallback. If the
   live demo dies, share that tab and narrate from the diagram.

---

## Spoken script (with screen cues)

**Time markers are spoken-time. Keep transitions short — no dead air.**

### 0:00 – 0:25 — Hook & problem (25 s)

> "Hi, we're Group 1 — and this is the **Multimodal AI Design Analysis
> Suite**. The problem: every design review at a real company is the same
> meeting on loop. A designer ships a screen, four reviewers re-derive the
> same checklist — visual, UX, accessibility, brand, market — and a week
> later somebody finally writes a memo. We replaced that meeting with a
> multi-agent panel that takes one screenshot and ships a prioritized,
> evidence-backed report in under thirty seconds."

**[SCREEN]** Hero band visible — "Design Analysis Suite" with the five
chips (Visual / UX / Accessibility / Brand / Market). Pause one beat so the
judges read the chips.

---

### 0:25 – 1:00 — Architecture in one breath (35 s — concept-dense)

> "Architecturally it's a **LangGraph** DAG. The graph fans out to **five
> specialist agents in parallel** with `asyncio.gather`, each one grounded
> by **image RAG** over a **CLIP-embedded LanceDB index** of reference
> designs, plus **Tavily** web search for live market signals. Every agent
> calls **multimodal GPT-4o or Claude 3.5 Sonnet over OpenRouter** with a
> **JSON-schema-constrained Pydantic** response, and a synthesizer agent
> rolls the five outputs into one ranked report. The full run is **traced
> in LangSmith**, **disk-cached** so re-runs cost zero, and exposed as an
> **MCP server** — so Claude Code or any MCP-compatible IDE can use our
> agents as tools. That covers eleven of the accelerator concepts in one
> screenshot."

**[SCREEN]** Briefly hover over the **steps strip** (Upload → Add context →
Review). Don't click anything yet.

> *(If you have an extra ten seconds, also say: "and yes — image is sent
> directly to the LLM as a base64 data URL with EXIF correction and a 1024
> px max-side resize, not OCR-then-text. The vision model sees the pixels
> the user sees.")*

---

### 1:00 – 2:30 — Live demo (90 s)

**[SCREEN]** Click **Run analysis**.

> "I'll run it on the bundled fintech dashboard sample. Watch the status
> bar — every agent logs start, finish, and any retry. That's deliberate:
> when a teammate's call fails at 2 a.m., we don't want a silent hang."

**[SCREEN]** As the status changes, narrate over it:

> "Visual agent measures hierarchy and density. UX critiques task flow
> against Nielsen's heuristics. Accessibility runs a WCAG-style contrast
> and target-size check. Brand-consistency compares the screen against our
> indexed reference set in LanceDB. Market-research pulls live web signals.
> The synthesizer composes a ranked recommendation list with effort and
> impact tags."

**[SCREEN]** Click the **Report** tab the moment the score appears.

> "There's the score — 76.4 out of 100. Top strengths first, then
> prioritized recommendations as cards. Each one has an **Effort** tag in
> gold and an **Impact** tag in teal — that's the whole point of the
> synthesizer: it has to argue why a fix is worth the work."

**[SCREEN]** Click **References** tab. Type `fintech dashboard onboarding`,
hit Enter.

> "The References tab is image RAG plus live web. Local results come from
> our LanceDB vector store — these thumbnails are real screens we
> ingested. Live web results come from Tavily, free-tier-fallback to
> DuckDuckGo. Together that's how brand-consistency and market-research
> get their evidence — we don't let agents hallucinate citations."

**[SCREEN]** Click **Settings** tab.

> "Settings is the deployability story. Real-API key loaded, indexed
> reference rows, report directory — all from a single `.env` file. The
> whole app deploys to Hugging Face Spaces for free, which is in our FAQ."

---

### 2:30 – 3:15 — Difficulty + Code-quality proof (45 s)

**[SCREEN]** Switch to terminal. `cat tests/ -1 | head` or just run
`pytest -q` so judges see green.

> "On code quality: **88 tests pass**, ruff and black are clean across the
> repo, every module carries a standard `OWNER / CONCEPTS / CONSUMES /
> PROVIDES` header so a new teammate can read the dependency graph in
> thirty seconds. We use **dependency injection with Protocol classes**,
> so every agent has a deterministic **fake** alongside the real
> implementation — that's how we wrote five people's tests in parallel
> without anyone needing an OpenRouter key."

**[SCREEN]** Optional: open `docs/walkthrough.html` and scroll the
architecture diagram for one beat.

> "On difficulty: this is **multimodal vision**, structured output that
> survives schema drift via a JSON-mode fallback, parallel agent
> orchestration, retrieval-augmented generation, an MCP server, and a
> cost-aware disk cache — under thirty seconds end-to-end on a real run.
> One person could not have built this; five people on five branches did,
> integrated cleanly through Protocol-shaped seams."

---

### 3:15 – 3:50 — MCP wow-moment + close (35 s)

**[SCREEN]** Open a second terminal, run `make mcp` (or
`python -m src.mcp.server`).

> "And one last thing — because the agents are exposed as an MCP server,
> any MCP-compatible client like Claude Code can call our visual analysis
> as a tool. That means the same engine that powers this UI can sit
> *inside* an engineer's IDE while they ship a feature. It's the same
> agent code — we just changed the surface."

**[SCREEN]** Return to the Gradio Report tab so the score is the last
visual.

> "So — eleven accelerator concepts, multimodal end-to-end, eighty-eight
> green tests, deployable on Hugging Face for under a dollar a day, and
> the whole thing is open source. That's our submission. Thank you."

---

## Concept-count cheat sheet (memorize)

If a judge asks "which accelerator concepts did you use?", answer in this
order — every item is a thing they can verify in the repo:

1. **Multimodal LLMs** — `src/llm/multimodal.py`, GPT-4o / Claude vision.
2. **Structured output / JSON schema** — `src/schemas/outputs.py`,
   Pydantic v2 plus `response_format={"type":"json_schema", ...}`.
3. **AI Agents (multi-agent panel)** — `src/agents/*.py`, five specialists
   plus a synthesizer.
4. **Agent orchestration** — `src/agents/graph.py`, LangGraph DAG.
5. **Parallel async fan-out** — `asyncio.gather` in the graph node.
6. **Image RAG** — `src/rag/embedder.py` + `src/rag/vector_store.py`,
   CLIP-on-LanceDB.
7. **Web search tool** — `src/tools/web_search.py`, Tavily with
   DuckDuckGo fallback.
8. **Observability / tracing** — `src/utils/tracing.py`, LangSmith with a
   no-op fallback.
9. **Cost optimization** — `src/llm/cost.py`, disk-backed `@cached`
   decorator, image resize, temperature 0.2 for cache hit rate.
10. **Evaluation harness** — `src/evals/harness.py`, deterministic fakes,
    schema-validated regression checks.
11. **MCP server** — `src/mcp/server.py`, exposes the same agents to any
    MCP-compatible IDE.
12. **Open-source-only stack** — Gradio UI, LangChain, LangGraph,
    LanceDB, open_clip, Pillow, OpenCV, Pydantic. Full license audit in
    `docs/FAQ.md`.

---

## Backup lines if something breaks live

| Failure                           | Spoken recovery                                                                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenRouter rate-limit / 429       | "We hit a real-API rate limit — that's why we have offline fakes. Let me flip the toggle." Uncheck "Use real APIs", click Run again, fakes return in 1 s. |
| Gradio fails to load              | "Live demo is down — the architecture is the same; let me walk through `docs/walkthrough.html` instead." Switch to the HTML walkthrough tab.             |
| LanceDB shows zero indexed rows   | "References live-search needs `make ingest`. The Tavily side still works — let me show that path." Skip local thumbnails, narrate the web-results card.  |
| Tavily key missing                | "We fall back to DuckDuckGo automatically — no judge sees a blank page." Carry on; the search returns DDG hits.                                          |
| Schema validation error in report | "That's the eval harness catching a bad agent output — exactly what we built it for." Open the warning log and read the agent name + bad field.          |
| MCP server fails to bind          | "MCP runs in any compatible IDE; the binding is just for this laptop." Skip the live MCP step, point at `src/mcp/server.py` in the file tree.            |

---

## 5-minute extended cut (if judges ask for more)

After the standard close, add this 60-second appendix:

> "Two things we'd ship next. **First, an offline fallback model** — we
> already have a Hugging Face local-LLM stub at `src/llm/hf_local.py`, so
> a Qwen 2.5 0.5B can answer when there's no internet. Demo runs on a
> laptop. **Second, a model council** — right now every agent calls one
> model; the synthesizer is the council. The cleanest extension is to
> give each agent two models — GPT-4o and Claude — and have the
> synthesizer arbitrate disagreements. That's a one-week change because
> our LLM client is already a Protocol — you swap the implementation, not
> the agent. Both ideas are documented as TODOs in the per-person README
> files so the next cohort can pick them up."

---

## One-line elevator pitch (for the Q&A)

> "It's a multi-agent multimodal design reviewer. Five specialists run in
> parallel against image RAG and live web, a synthesizer ranks the fixes,
> and the whole thing is exposed both as a Gradio app and as an MCP server
> — so the same engine ships to designers and to engineers in their IDE."
