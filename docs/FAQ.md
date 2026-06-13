# FAQ — design choices, deployment, costs, debugging

This file answers the questions every reviewer (and every teammate joining
late) will ask. Keep it short, blunt, and source-of-truth.

---

## 1. Why is the default `temperature = 0.2`? Isn't the chat default 0.7?

**Short answer:** every LLM call in this codebase is a structured-output call
(JSON-schema mode). For structured output the right default is *low*.

| Goal of the call | Right temperature |
| --- | --- |
| Free-form chat with a human | 0.7 – 1.0 (the OpenAI / OpenRouter default for chat) |
| Structured JSON adherence to a schema | 0.0 – 0.3 |
| Code generation | 0.0 – 0.2 |
| Brainstorm / divergent ideation | 0.7 – 1.2 |

We picked **0.2** for these specific reasons:

1. **Schema adherence.** At 0.7 the model adds extra fields, swaps types
   ("color: navy" instead of "#0A2540"), and occasionally wraps the JSON in
   markdown. At 0.2 these are rare. ``model_validate_json`` would still
   catch them, but the eval harness flake-rate goes from ~5 % to <1 %.
2. **Cache hit rate.** Same inputs → same outputs. The disk cache in
   `src/llm/cost.py` saves $$$ on the demo. At 0.7 the same prompt gives
   different output each time; the cache is technically still hit (key is
   the *input* hash), but you lose the reproducibility judges want when
   they re-run the demo.
3. **Eval determinism.** The schema-validity eval (`scripts/run_evals.py`)
   needs to compare runs across days. Higher temperature means flaky pass
   rates that erode trust in the metric.

**When to override:** the Market Research agent's brainstorm step might
benefit from 0.5-0.7. Do that *per-call*, not by changing the default:

```python
deps.llm.complete(system=..., user=..., schema=..., temperature=0.6)
```

The reasoning is now also embedded in `src/config.py` next to the field.

---

## 2. How are images passed to the LLM? OCR? Captions? Direct?

**Short answer:** direct, as base64-encoded data URLs in the OpenAI
multimodal Chat Completion API. **No OCR step**, **no captioning step**.

### What actually happens (Step 1 → user uploads `dashboard.png`)

```
Pillow (RGB, EXIF-corrected, resized to 1024 px max side)
    ↓
PNG bytes
    ↓
base64.b64encode  →  "data:image/png;base64,iVBORw..."
    ↓
{ "type": "image_url", "image_url": { "url": "data:..." } }
    ↓
chat.completions.create(model="gpt-4o-mini", messages=[ {role:"user", content:[text, image]} ],
                        response_format={"type":"json_schema","json_schema":{...}})
    ↓
JSON string  →  Pydantic.model_validate_json  →  typed VisualAnalysis
```

That's the WHOLE pipeline. No Tesseract, no BLIP captions, no intermediate
text representation. The vision LLM sees the raw image and does its own
OCR / pattern recognition / layout reasoning internally.

### Why not OCR + text?

- **Quality.** The vision LLM has trained on screenshots end-to-end. An
  OCR + caption pipeline strips spatial relationships ("the red button is
  to the right of the input"), which is exactly what UX critique needs.
- **Tokens.** OCR'd HTML/text of a 4 K screenshot is often 5-10 K tokens.
  The same screenshot at 1024 px is ~700 tokens. Direct image is cheaper.
- **Maintenance.** Two pipelines to keep in sync vs one.

### Where the image-passing code lives

- `src/llm/multimodal.py::encode_image_to_data_url` — the encoder.
- `src/llm/multimodal.py::vision_message` — builds the OpenAI payload.
- `src/llm/multimodal.py::OpenRouterVision.analyze` — the call site.
- `src/tools/image_utils.py::side_by_side` — composites multiple images
  into one to *halve* the upload cost when comparing N references.

### What we'd add post-MVP

- **Tile mode** for huge images: split a 6 K × 4 K screenshot into 4 quadrants
  and let the model see each at full resolution, then ask a final pass to
  reason across tiles. (gpt-4o supports this natively as `detail: "high"`.)
- **Lightweight OCR fallback** for accessibility text-size measurement
  (Tesseract). Currently the LLM estimates font sizes; a Person D extension.

---

## 3. Is this like Perplexity's "model council" with one model?

**Short answer:** No. Perplexity Pro Search uses *one* model per query
(picked by the user) or rotates *across* models for ensemble. We use
**one model with five different agent personas** running in parallel —
this is a "panel of experts" / multi-agent pattern, not model council.

### Mental model

| Pattern | "Many models, one prompt" | "One model, many roles" | Our system |
| --- | --- | --- | --- |
| Perplexity Pro | ✅ | ❌ | — |
| Model Council (e.g. arena) | ✅ | ❌ | — |
| LangGraph multi-agent | ❌ | ✅ | **✅** |
| Crew AI | ❌ | ✅ | — (but similar) |

The five agents (Visual / UX / A11y / Brand / Market) are differentiated by:
- **System prompt** (each has its own persona and rubric in `src/utils/prompts.py`).
- **Output schema** (each emits a different Pydantic class).
- **Inputs** (4/5 use the image; Market uses text + web search results).
- **Tools available** (only Brand uses the Retriever; only Market uses Web Search).

They all hit the same vision/text LLM by default. The synthesizer then
fan-ins across all five into one `DesignReport`.

### How to convert this into a real model council

Person A's `src/llm/cost.py::select_model` is the seam. Today it returns
the same default. Wire it like this:

```python
def select_model(task: str = "default") -> str:
    return {
        "visual":        "openai/gpt-4o",                # best at color/layout
        "ux":            "anthropic/claude-3.5-sonnet",  # best at narrative critique
        "accessibility": "openai/gpt-4o-mini",           # cheap, schema-following
        "brand":         "openai/gpt-4o",                # multimodal compositing
        "market":        "google/gemini-pro-1.5",        # web context window
        "synthesizer":   "anthropic/claude-3.5-sonnet",  # best at ranking
    }.get(task, settings.default_text_model)
```

Then each agent calls `deps.llm.complete(..., model=select_model("visual"))`.
That gives you Perplexity-style cross-model diversity with a single
OpenRouter key (OpenRouter routes to all of these). Documented as post-MVP
because picking 6 models means 6 prompt iterations — too much for 48 hours.

---

## 4. Will this app run on Hugging Face Spaces or Vercel? (Cost-conscious deploy)

### TL;DR

| Platform | Verdict | Why |
| --- | --- | --- |
| **Hugging Face Spaces** | **Recommended** | Gradio is HF's first-class framework. Free CPU tier exists. Persistent disk for LanceDB available on paid tier. |
| Vercel | **Not recommended** | Vercel's serverless model hates long-running Python + persistent disk. Gradio works in a hack-y way; you'd rebuild the UI in Next.js. |
| Render / Fly.io | Works fine | Long-running container, persistent disk. Reasonable middle ground. |
| Local laptop | The hackathon demo target | Zero cost. Use this. |

### Hugging Face Spaces — the recommended path

1. Create a Space, pick **Gradio** SDK, hardware **CPU basic (free)** or
   **CPU upgrade ($0.03/hr)**.
2. Push the repo. HF auto-detects `requirements.txt` and `ui/app.py` via the
   `app.py` convention or a `Spaces` config.
3. Set secrets (HF Spaces "Variables and secrets"):
   - `OPENROUTER_API_KEY` — required
   - `TAVILY_API_KEY` — optional (DuckDuckGo fallback works)
   - `LANGCHAIN_API_KEY` + `LANGCHAIN_TRACING_V2=true` — optional
   - `USE_REAL=1` — flip to real APIs
4. For LanceDB persistence, either:
   - Pay for **Persistent Storage** ($5/mo for 20 GB) and point
     `VECTOR_STORE_DIR` at `/data/vector_store`; OR
   - Re-ingest on container boot from a HuggingFace Dataset (free, slower).

The Gradio app already uses port 7860 (HF default), so no UI code change.

### Vercel — why we don't recommend it

- Vercel is built for **Next.js + Edge functions**. Python is a second-class
  runtime via `@vercel/python`.
- Function timeout: 10 s on Hobby, 60 s on Pro. Our graph runs five LLM
  calls plus a synthesizer — under 60 s only with cache hits.
- **No persistent disk.** LanceDB needs ≥ 100 MB local disk. Workaround =
  external Lance/S3, which doubles the architecture for no gain.
- Gradio doesn't ship a serverless adapter. You'd rewrite the UI as a
  Next.js + REST API, doubling the work for hackathon week.

### Cost-conscious deployment checklist

- [ ] `USE_REAL=1` only when needed (judge demo). Default to fakes during dev.
- [ ] Cache enabled (`CACHE_DISABLED` unset). One demo run hits cache on
      every replay → free.
- [ ] Use `openai/gpt-4o-mini` (~$0.15 / 1M input tokens). Switch to
      `gpt-4o` only for the demo if the difference is visible.
- [ ] Set `default_max_tokens=1024` for non-synthesizer agents — saves
      ~30 % on token spend.
- [ ] Tavily — leave the env var unset until needed. DuckDuckGo is free.
- [ ] LangSmith — enable only on demo day. Free tier = 5 K traces/month;
      one full demo run uses ~6 traces.

Order-of-magnitude budget for one full demo run end-to-end with real APIs:

- 5 vision-LLM calls × 1.5 K tokens × $0.15/1M ≈ $0.001
- 1 text synth × 4 K tokens × $0.15/1M ≈ $0.001
- 5 Tavily queries × $0.005/query ≈ $0.025
- **Total: ≈ $0.03 / run.** With cache, repeat runs are free.

---

## 5. Open-source vs paid? License audit per dependency

All Python libraries we import are open source. The **services** they hit
may be paid SaaS — the table is explicit about which is which.

| Library / service | Type | License | Cost | Substitute |
| --- | --- | --- | --- | --- |
| `openai` (SDK) | OSS lib | Apache-2.0 | Free | — |
| OpenRouter (the gateway it points at) | Paid SaaS | — | ~$0.15/1M tokens for `gpt-4o-mini` | Self-host vLLM (post-MVP) |
| `pydantic`, `pydantic-settings` | OSS | MIT | Free | — |
| `gradio` | OSS | Apache-2.0 | Free | Streamlit (Apache-2.0) |
| `langgraph`, `langchain-core` | OSS | MIT | Free | hand-roll asyncio fan-out |
| `lancedb` | OSS | Apache-2.0 | Free (embedded) | Qdrant (Apache-2.0), Chroma (Apache-2.0) |
| `open-clip-torch` | OSS | MIT | Free | sentence-transformers (Apache-2.0) |
| `torch`, `torchvision` | OSS | BSD-style | Free (CPU) | — |
| `Pillow` | OSS | MIT-CMU | Free | — |
| `llama-index` | OSS | MIT | Free (concept claim only) | — |
| `tavily-python` | OSS lib | MIT | **SaaS is paid** ($0.005/query, 1K free/month) | DuckDuckGoSearch (MIT, free) |
| `duckduckgo-search` | OSS | MIT | Free | — |
| `mcp` (Python SDK) | OSS | MIT | Free | — |
| `langsmith` (SDK) | OSS | Apache-2.0 | **SaaS has free tier** (5 K traces/month) | print + JSON dump |
| `loguru`, `rich` | OSS | MIT | Free | — |
| `pytest`, `ruff`, `black`, `mypy` | OSS | MIT/BSD | Free | — |

**No proprietary library is required.** Three optional SaaS endpoints are
on the demo path; each has a working free fallback in the codebase:

| SaaS | Required? | Fallback |
| --- | --- | --- |
| OpenRouter | Yes for `USE_REAL=1` | `FakeLLM` / `FakeVisionLLM` (already wired) |
| Tavily | No | `DuckDuckGoSearch` (auto-selected when key absent) |
| LangSmith | No | `traced(...)` is a no-op without a key |

Replacing OpenRouter with self-hosted vLLM/Ollama is a *one-line change*
in `src/llm/openrouter_client.py` (`base_url`). Documented as post-MVP.

---

## 6. Will I see error messages when I run? (Debugging story)

Yes. Three principles guarantee visible errors:

1. **Every LLM call goes through `run_with_schema`** in `src/agents/base.py`,
   which logs `INFO` on entry, `ERROR` on exception (with full type+message),
   then re-raises. You will see things like:
   ```
   14:25:01 INFO   agent.visual: starting (schema=VisualAnalysis, images=1)
   14:25:03 ERROR  agent.visual: failed: openai.RateLimitError: rate limit exceeded
   ```
2. **No `except Exception: pass`** anywhere on the critical path. The only
   broad-except is in the eval harness (it deliberately scores past one
   bad field), and that one logs `WARNING` with which field failed.
3. **Loguru → stderr by default**, level = INFO. To bump to DEBUG for a
   single run:
   ```bash
   LOG_LEVEL=DEBUG python -m src.agents.graph --image data/uploads/dashboard.png
   ```

Per-slice quick-debug commands:

```bash
make run-c-visual        # Person C — visual analysis only, prints JSON
make run-c-brand         # Person C — brand consistency only
make run-d-ux            # Person D — UX critique only
make run-d-a11y          # Person D — accessibility only
make run-e-market        # Person E — market research only
make run-a-graph         # Person A — full graph end-to-end
```

Each prints an INFO line per agent and a final JSON dump to stdout. If
something fails, the ERROR line tells you which agent and why.

---

## 7. Why is there an MCP server? Couldn't users just hit the Gradio UI?

**Short answer:** the Gradio UI is for *humans*. The MCP server is for
*other AI agents* — and that turns the suite into a tool that any
AI-powered IDE or coding agent can call as if it were native.

### What MCP actually is

MCP = **Model Context Protocol**. It's an open wire-protocol standard
(JSON-RPC over stdio or HTTP) that lets a host LLM application
(Claude Code, Continue, Cline, Zed, or any future client) discover and
invoke external tools at runtime. Same idea as "function calling" but
*portable across hosts*.

```
Host LLM agent (Claude Code, etc.)
        │   spawns
        ▼
mcp.json  →  python -m src.mcp.server
        │   stdio JSON-RPC
        ▼
Our two tools:
  - analyze_design(image_path, instructions?) → DesignReport
  - search_designs(query, k=5)               → list[RetrievedRef]
```

### Why we ship one

Five concrete reasons, ordered by demo value:

1. **Sprint 4 of the curriculum requires it.** We have to demonstrate MCP.
   Without `src/mcp/server.py`, we lose ~1.5 points on Concept Score (and
   it's the cheapest concept to claim — ~80 lines of wiring).
2. **Interoperability without a custom integration.** A designer using
   Claude Code can run `@design-suite analyze_design dashboard.png` and
   get the same DesignReport — without us building a Claude Code
   extension, a VS Code plugin, a JetBrains plugin, etc. One server,
   every client.
3. **The "wow" moment of the demo.** Tab 1 is "I built a Gradio UI"
   (boring — everyone does that). Tab 2 is "I exposed the same graph as a
   wire-protocol tool that another AI agent can call inline" (judges sit
   up). Same backend; two completely different surface areas.
4. **Programmatic access without auth.** A teammate can script
   "analyze every PNG in `data/uploads/`" against the MCP server in 5
   lines of Python — no Gradio session, no scraping, no API key
   plumbing on the client side (the server inherits its env from the
   host).
5. **Composability with other tools.** Once `analyze_design` is an MCP
   tool, the host LLM can chain it: *"Read this Figma export, run
   analyze_design on the largest frame, then write a Slack summary."*
   That's the agentic workflow story we're claiming for Sprint 6.

### What it is NOT

- **Not a REST API.** No HTTP server, no FastAPI, no auth tokens. MCP is
  stdio-first; the host launches us as a subprocess.
- **Not a replacement for the UI.** Designers still want the UI for
  drag-drop and the gallery. MCP is for engineers who already live in a
  chat panel.
- **Not a way to expose the suite to the public internet.** stdio means
  one host, one trusted user. HTTP transport is documented as post-MVP.

### What sits in `src/mcp/server.py`

Two tool functions plus a stdio bootstrap. Skeleton today; Person E
fills the `@server.tool()` decorator wiring per the recipe in the file.
The tool functions themselves (`analyze_design_tool`,
`search_designs_tool`) already work — the only thing missing is the
JSON-RPC plumbing that hands them to the protocol.

See also: `src/mcp/server.py` top docstring, the demo magic-moment line
in `docs/DEMO_SCRIPT.md`, and the MCP tab in `docs/walkthrough.html`.

---

## 8. Where do these answers live in the code?

| Question | Source-of-truth file |
| --- | --- |
| Temperature reasoning | `src/config.py` (next to the field) |
| Image-passing path | `src/llm/multimodal.py` (top docstring) |
| Multi-agent vs model-council | `src/agents/graph.py` (top docstring) + `select_model` in `src/llm/cost.py` |
| OSS vs paid SaaS | `requirements/*.txt` headers + this FAQ |
| Logging contract | `src/agents/base.py::run_with_schema` |
| Deployment | `README.md` "Deploy" section + this FAQ |
| MCP server purpose | `src/mcp/server.py` top docstring + this FAQ § 7 |
