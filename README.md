# Multimodal AI Design Analysis Suite

> A multi-agent LangGraph system that reviews uploaded UI/product designs.
> Five specialists run in parallel — visual, UX, accessibility, brand, and
> market — over an image-RAG corpus. The synthesizer aggregates everything
> into a typed `DesignReport`. Built for the C7 Engineering Accelerator
> hackathon.

## What it does

1. Drag a design screenshot into the Gradio UI (or call `analyze_design`
   over MCP from Claude Code or any other MCP-compatible client).
2. Five specialist agents fan out concurrently. Each returns a Pydantic
   model — no markdown, no prose.
3. The synthesizer aggregates the five outputs into a `DesignReport` with
   top-3 strengths, top-5 prioritized recommendations, and an overall score.

## Architecture (one mermaid diagram)

```mermaid
flowchart TB
    User --> UI[Gradio UI]
    UI --> Graph[LangGraph Orchestrator]
    Graph --> Visual & UX & A11y & Brand & Market
    Visual & UX & A11y & Brand & Market --> Synth[Synthesizer]
    Synth --> Report[DesignReport JSON]
    Brand -.uses.-> RAG[Image RAG<br/>CLIP + LanceDB]
    Market -.uses.-> Web[Tavily / DuckDuckGo]
    Visual & UX & A11y & Brand -.uses.-> LLM[OpenRouter]
    External[Claude Code / MCP client] -.MCP.-> Graph
```

The full diagram set lives in `docs/ARCHITECTURE.md` and the interactive
walkthrough in `docs/walkthrough.html`.

## Quickstart

### Run the offline path first (no keys, no network, no GPU)

**Linux / macOS:**

```bash
git clone <this-repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" -r requirements/all.txt
make test                        # 56 tests, ~8 seconds
make run-a                       # full graph against the bundled sample, all fakes
```

**Windows (PowerShell):**

```powershell
git clone <this-repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -e ".[dev]" -r requirements/all.txt
# `make` is not native on Windows. Either install GnuWin32 / Chocolatey
# `choco install make` (recommended), or run the equivalent commands directly:
pytest -q                                   # equivalent to `make test`
python -m src.agents.graph --image src/fakes/fixtures/sample.png  # equivalent to `make run-a`
```

> Every Makefile target maps to a one-line `python -m ...` command. Open
> the `Makefile` (it's short, ~50 lines) to see the equivalent if you'd
> rather not install `make`.

### Switch on real APIs

1. **Get an OpenRouter key** at https://openrouter.ai/keys (sign in → "Create
   Key"). Add $5 of credits — that lasts the entire hackathon.
2. (Optional) **Tavily** at https://app.tavily.com/home for nicer market-
   research snippets — 1,000 queries/month free. Skip it and the code falls
   back to free DuckDuckGo automatically.
3. (Optional) **LangSmith** at https://smith.langchain.com/settings →
   "API Keys" for traces — 5,000 traces/month free.

**Copy the env template:**

```bash
# Linux / macOS:
cp .env.example .env

# Windows (PowerShell):
Copy-Item .env.example .env
```

Open `.env` in your editor and edit at minimum:

```
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-...                        # optional
LANGCHAIN_API_KEY=lsv2_pt_...                  # optional
LANGCHAIN_TRACING_V2=true                      # optional
USE_REAL=1                                     # flip 0 → 1
```

**Verify the key loaded** (works on every OS):

```bash
python -c "from src.config import settings; print('OR key set:', bool(settings.openrouter_api_key))"
# Expect:  OR key set: True
```

**Run end-to-end:**

```bash
# Linux / macOS:
make ingest                                        # build the LanceDB corpus from data/reference/*.png
USE_REAL=1 make ui                                 # Gradio at http://127.0.0.1:7860

# Windows (PowerShell):
python -m scripts.ingest_references --source .\data\reference
$env:USE_REAL="1" ; python -m ui.app
```

Per-slice setup (just *your* keys, just *your* deps) is in
`docs/PERSON_<A|B|C|D|E>.md` — each starts with a "Setup — first 5 minutes"
block listing exactly which keys you personally need and which you can
skip.

## Per-person quickstart

| Person | Slice | Install | Smoke run |
|---|---|---|---|
| A | Infra & orchestration | `make install-a` | `make run-a` |
| B | Image RAG | `make install-b` | `make ingest && make run-b` |
| C | Visual + Brand agents | `make install-c` | `make run-c-visual && make run-c-brand` |
| D | UX + Accessibility agents | `make install-d` | `make run-d-ux && make run-d-a11y` |
| E | Market + UI + MCP | `make install-e` | `make ui` and `make mcp` |

Per-person READMEs in `docs/PERSON_*.md` explain the mission, contracts,
hot-spots, and "done when" checklist for each slice.

## Repo layout

```
src/
  config.py            settings (pydantic-settings)
  contracts.py         Protocol classes - the seams between people
  schemas/outputs.py   every cross-module Pydantic model
  fakes/               deterministic doubles for offline development
  llm/                 OpenRouter, multimodal, cost cache, HF stub
  rag/                 CLIP embedder, LanceDB store, retriever
  tools/               web_search, image_utils, rag_tool (LangChain wrapper)
  agents/              base + 5 specialists + synthesizer + graph
  utils/               logger, prompts, tracing
  evals/               schema-validity harness
  mcp/server.py        stdio MCP server (analyze_design, search_designs)
ui/app.py              Gradio Blocks
scripts/               ingest_references, run_evals
tests/
  conftest.py          shared fixtures
  test_{schemas,contracts,fakes}.py    cross-cutting (everyone runs)
  person_a..e/         per-slice tests
docs/
  PERSON_*.md          per-person READMEs
  ARCHITECTURE.md, DEMO_SCRIPT.md, CONCEPT_COVERAGE.md
  walkthrough.html     self-contained interactive flow demo
```

## Concept coverage

See `docs/CONCEPT_COVERAGE.md` for the full mapping of accelerator concepts
to file paths. Every Sprint 1-6 has a real artifact the judges can point at.

## FAQ — design choices, deployment, debug

`docs/FAQ.md` answers the recurring questions:

- Why `temperature=0.2` (not the chat default 0.7)?
- How are images passed to the LLM (data URLs, no OCR)?
- Is this a "model council" like Perplexity? (No — panel of experts.)
- Will it run on Hugging Face Spaces / Vercel? (Yes / no.)
- Is everything open-source? (Libraries yes; OpenRouter is paid SaaS but
  every paid service has a working free fallback wired in.)
- Will errors be visible when I run? (Yes — every agent boundary logs.)
- Why is there an MCP server? (Sprint 4, plus the demo magic moment —
  any MCP-compatible coding agent can call our graph as a native tool.)

## Deploy

| Target | Verdict | Notes |
|---|---|---|
| Hugging Face Spaces (Gradio SDK) | **Recommended** | Free CPU tier; LanceDB via paid Persistent Storage ($5/mo) or re-ingest from a HF Dataset on boot |
| Render / Fly.io | Works fine | Long-running container + persistent disk |
| Vercel | Not recommended | Serverless 60 s timeout, no persistent disk; would require rewriting Gradio as Next.js |
| Local laptop | Hackathon demo target | Zero cost |

Cost-conscious budget for one full demo run with real APIs: **≈ $0.03**
(~5 vision LLM calls + 1 synth + 5 Tavily queries). With cache, repeats
are free. Full breakdown in `docs/FAQ.md` § 4.

## What we did NOT build (honest list)

- Production-scale orchestration (Celery / Temporal). Replaced by in-process
  LangGraph plus a documented swap.
- Distributed Redis cache. Replaced by a disk-backed JSON cache.
- Multi-tenant LanceDB / per-tenant API keys. Single tenant for v1.
- HTTP MCP transport. stdio only.
- LLM-as-judge in evals. Schema-validity only — accurate enough for judging.
- Pre-commit hooks. `make fmt && make lint` is the discipline.

The full "what we'd do for production" list is in
`docs/walkthrough.html` → **Scaling** tab.

## Tech stack

OpenRouter via `openai` SDK · LangGraph · LangChain-core · LangSmith ·
LanceDB · open_clip_torch · LlamaIndex (concept claim) · Pydantic v2 ·
Gradio · Tavily / DuckDuckGo · MCP Python SDK · pytest · ruff · black · mypy.

One library per concept — no duplicates.

## License & acknowledgements

MIT. Built by the C7 Hackathon Multimodal Group 1. Thanks to the Engineering
Accelerator Program for an excellent curriculum.
