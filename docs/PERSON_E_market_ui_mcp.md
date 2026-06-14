# Person E — Market Research + UI + MCP

> **Mission.** You are the demo. UI + market intel + MCP are what the judges
> actually see. If your tabs are clean and your tools work over MCP, the
> Difficulty score and Code-Quality score both go up by points.

## Why your slice exists (concepts you are demonstrating)

| Sprint | Concept | What you ship |
|---|---|---|
| 2 | Gradio | `ui/app.py` |
| 4 | MCP server | `src/mcp/server.py` |
| 5 | Tool-augmented agent (web search) | `src/agents/market_research.py` + `src/tools/web_search.py` |
| 6 | One more parallel branch of the fan-out | `src/agents/market_research.py` |

The MCP integration is the *unique* differentiator versus other hackathon
projects: nobody else will let judges call your graph from a coding-agent
chat panel (Claude Code, etc.) over a wire protocol.

## Files you own

| File | One-line purpose |
|---|---|
| `src/agents/market_research.py` | `run(state, deps)` → `{"market": MarketResearch}`. |
| `src/tools/web_search.py` | `TavilySearch`, `DuckDuckGoSearch`, default selector. |
| `src/rag/editorial_refs.py` | Hand-curated fallback when web search returns empty. |
| `ui/app.py` | Gradio Blocks entry point + `main()`. |
| `ui/strings.py` | All static guide-card / tip / placeholder HTML strings used by `ui/app.py` (extracted to keep `app.py` focused on wiring; named `strings` not `copy` to avoid shadowing the stdlib `copy` module when launched as `python ui/app.py`). |
| `ui/state.py` | Settings refresh + status / settings cards / telemetry. |
| `ui/handlers.py` | `on_run` (multi-frame aware streaming handler) + graceful error classifier + `_resolve_frame_labels`. |
| `ui/render.py` | Premium DesignReport HTML rendering — frame strip, per-frame heatmap, `affected_frames` badges. |
| `ui/references.py` | References-tab payload (surfaces `matched_frames` per gallery item) + ad-hoc search. |
| `ui/styles.py` + `ui/static/app.css` | App CSS (real .css file) + light-theme JS / HEAD. |
| `app.py` (root) | HF Spaces entry shim — imports `ui.app:main`. |
| `requirements.txt` (root) | HF Spaces dependency manifest. |
| `src/mcp/server.py` | stdio MCP server with two tools (`analyze_design` accepts `image_paths` + `frame_labels`). |
| `tests/person_e/*`, `tests/test_safe_image.py`, `tests/test_prompts.py`, `tests/test_editorial_refs.py` | Your test slice + new-feature tests you helped land. |

## Contracts you implement / consume

You **implement** `WebSearch`:

```python
class WebSearch(Protocol):
    def search(self, query, k=5) -> list[SearchResult]: ...
```

You **consume** `LLMClient` (and indirectly the compiled graph for the UI
and MCP tools).

### Multi-frame contract you exposed (UI + MCP)

| Surface | Multi-frame entry point | Notes |
| --- | --- | --- |
| Gradio Analyze tab | `gr.File(file_count="multiple")` + `frame_labels_in` textbox | `_resolve_frame_labels` pads with filename stems; preflight caps at 5 |
| MCP `analyze_design` | `image_paths: list[str]` + `frame_labels: list[str]` | Single-frame `image_path: str` still works (legacy) |
| Market agent prompt | `<product_context>` block when N>1 frames | Anchors competitor / trend selection on full product surface |
| References tab | `matched_frames` appended to gallery labels | Visible when N>1; empty for single-frame |

## Setup — first 5 minutes (do exactly this)

### 1. Clone and create a venv

**Linux / macOS:**

```bash
git clone <repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-e-ui.txt
```

**Windows (PowerShell):**

```powershell
git clone <repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-e-ui.txt
```

This installs Gradio + Tavily SDK + DuckDuckGo + the MCP Python SDK.

### 2. Keys you need (you sign up for two — Tavily is yours alone)

| Key | Mandatory for Person E? | Where to get it | Free tier? |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** for `USE_REAL=1` (the Market Research agent calls a text LLM with the search snippets) | https://openrouter.ai/keys | Pay-as-you-go |
| `TAVILY_API_KEY` | **Optional** but recommended (snippets are cleaner than DuckDuckGo) | https://app.tavily.com/home → "API Keys" | Yes — 1,000 queries/month |

If you skip Tavily, the codebase auto-falls back to `DuckDuckGoSearch` (no key, no signup) — see `src/tools/web_search.py::get_default_search`.

### 3. Copy and fill `.env`

```bash
# Linux / macOS:
cp .env.example .env

# Windows (PowerShell):
Copy-Item .env.example .env
```

**File to edit:** `./.env` (the file you just created at the repo root — NOT
`.env.example`, that's the template). Open it in your editor.

Make up to **three edits** — find each "before" line and replace it with
the "after" line. Line numbers reference `.env.example`.

| Line | Before (find this) | After (replace with) | Required? |
|---|---|---|---|
| L10 | `OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME` | `OPENROUTER_API_KEY=sk-or-v1-<paste your key>` | Yes for `USE_REAL=1` |
| L28 | `TAVILY_API_KEY=` | `TAVILY_API_KEY=tvly-<paste your key>` | Optional — leave blank to fall back to DuckDuckGo |
| L65 | `USE_REAL=0` | `USE_REAL=1` | Yes |

Leave every other line as-is. LangSmith (L49-50) is Person A's; you don't
need to touch it.

**Never commit `.env`.** It's already in `.gitignore`. Only `.env.example`
ships in git.

For the **MCP server**, the `.env` file is NOT used by your MCP client —
the client reads keys from the `env` block in its `mcp.json`. See Step 5
below for that snippet.

### 4. Verify your env loaded

```bash
python -c "from src.config import settings; print('openrouter:', bool(settings.openrouter_api_key)); print('tavily:', bool(settings.tavily_api_key)); from src.tools.web_search import get_default_search; print('default search:', type(get_default_search()).__name__)"
# Expect: openrouter: True   tavily: True   default search: TavilySearch
# (or DuckDuckGoSearch if you left tavily blank)
```

### 5. First successful run

```bash
make test-e                                        # offline (fakes) — should be green
make run-e-market                                  # against FakeSearch + FakeLLM
USE_REAL=1 make run-e-market                       # real web search + real LLM (~$0.005)
make ui                                            # Gradio at http://127.0.0.1:7860
make mcp                                           # stdio MCP server (test from any MCP client)
```

For the MCP server, paste this snippet into your MCP client's config file
(typical paths: `~/.config/claude-code/mcp.json` or whatever your client
documents — the schema is identical across MCP clients):

```jsonc
{
  "design-analysis-suite": {
    "command": "python",
    "args": ["-m", "src.mcp.server"],
    "cwd": "/abs/path/to/ai_c7_hackathon",
    "env": { "OPENROUTER_API_KEY": "sk-or-v1-...", "USE_REAL": "1" }
  }
}
```

## Run-in-isolation

```
make run-e-market                                       # uses FakeSearch
USE_REAL=1 TAVILY_API_KEY=... make run-e-market         # real Tavily
make ui                                                 # Gradio at http://127.0.0.1:7860
make mcp                                                # stdio MCP server
```

## Smoke tests

```
make test-e
```

## Implementation hot-spots

1. **`web_search.TavilySearch.search`** — wrap `TavilyClient().search(...)`,
   return `SearchResult` list. Cache to `data/cache/search/<sha>.json` for 24h.
2. **`ui/app.py:on_run`** — replace the single `run_graph` call with a per-node
   yield loop using `compiled.stream(state)` (once Person A wires LangGraph).
   Each yield should update the markdown log so the judge sees real-time
   progress.
3. **Tab 2 (Report)** — bind to a `gr.State` carrying the `DesignReport` from
   Tab 1. Render with `render_report(state)` (already a stub).
4. **Tab 3 (References)** — text input + gallery; on submit, call
   `deps.retriever.retrieve_by_text(text, k=12)` and display thumbnails.
5. **`src/mcp/server.py:main`** — wire `@server.tool()` for both tool functions
   then `await stdio_server()`. Provide an `mcp.json` snippet in the README so
   judges can paste it into their MCP client's config.

## Done when

- [ ] `make test-e` is green from a fresh `.venv`.
- [ ] Market agent yields `MarketResearch` with ≥2 competitors and ≥1 trend
      against a real screenshot (with `USE_REAL=1`).
- [ ] Gradio UI runs the full graph end-to-end and renders the `DesignReport`.
- [ ] `python -m src.mcp.server` lists `analyze_design` and `search_designs`.

## Common pitfalls

- **Tavily rate limits** — fall back to `DuckDuckGoSearch` cleanly. The
  selector `get_default_search()` already does the right thing.
- **Gradio file-upload path resolution on Windows** — use `image.name` (the
  `tempfile.NamedTemporaryFile` attribute Gradio sets), not the `path` kw.
- **MCP stdio buffering** — route loguru / stdlib logs to **stderr** so MCP's
  JSON-RPC stdout stays clean. The logger already does this; don't override.
- **Streaming progress updates** — `gr.update(...)` plus `yield (markdown, dict)`
  is the right shape; do not call `.update()` from inside a non-generator handler.
