# Architecture

This is the single page the demo MC reads aloud. The interactive version is
`docs/walkthrough.html` — open it in any browser, no build step required.

## Big picture

```mermaid
flowchart TB
    User[User] --> UI[Gradio UI<br/>ui/app.py + ui/state.py + ui/handlers.py]
    UI -- preflight + auto-resize --> Safety[Image safety gate<br/>src/utils/safe_image.py]
    Safety --> Orchestrator[LangGraph Orchestrator<br/>src/agents/graph.py]

    subgraph rag [Image RAG layer]
        Embed[CLIP Embedder<br/>src/rag/embedder.py]
        VStore[LanceDB Store<br/>src/rag/vector_store.py]
        Retr[Retriever<br/>src/rag/retriever.py]
        Editorial[Editorial Fallback<br/>src/rag/editorial_refs.py]
        Embed --> VStore --> Retr
    end

    subgraph pretools [Deterministic pre-tools — LangChain @tool]
        Palette[extract_palette<br/>k-means in CIELab]
        TextSize[estimate_text_size<br/>OpenCV CCA]
        CTA[cta_density<br/>keyword scan]
        DeltaE[palette_distance<br/>Δ-E in CIELab]
    end

    subgraph agents [LangGraph Specialist Agents]
        VA[Visual Analysis Agent]
        UX[UX Critique Agent]
        MR[Market Research Agent]
        AC[Accessibility Agent]
        BR[Brand Consistency Agent]
        SY[Synthesizer Agent + quality gate retry]
    end

    Orchestrator --> VA
    Orchestrator --> UX
    Orchestrator --> MR
    Orchestrator --> AC
    Orchestrator --> BR

    VA -.runs.-> Palette
    AC -.runs.-> TextSize
    UX -.runs.-> CTA
    BR -.runs.-> DeltaE

    VA --> SY
    UX --> SY
    MR --> SY
    AC --> SY
    BR --> SY

    SY --> Orchestrator
    BR -.uses.-> Retr
    BR -.fallback.-> Editorial
    MR -.uses.-> WebSearch[Tavily / DuckDuckGo<br/>src/tools/web_search.py]
    MR -.fallback.-> Editorial

    VA -.uses.-> LLM[Multimodal LLM<br/>src/llm/multimodal.py]
    UX -.uses.-> LLM
    AC -.uses.-> LLM
    SY -.uses.-> Text[Text LLM<br/>src/llm/openrouter_client.py]

    LLM --> OR[OpenRouter Gateway<br/>src/llm/openrouter_client.py]
    OR --> Telemetry[Cost tracker + circuit breaker<br/>src/llm/cost_tracker.py]
    Telemetry --> Cache[Disk-backed JSON cache<br/>src/llm/cost.py]

    Orchestrator -.traces.-> LS[LangSmith — opt-in]
    Orchestrator --> Report[DesignReport JSON<br/>data/reports/*.json]
    Report --> UI

    MCP[MCP Server<br/>src/mcp/server.py] -.exposes tools to.-> ExternalAgent[External agents<br/>Claude Code, MCP clients]
    MCP -.calls.-> Orchestrator
```

## The five robustness layers (what wraps the multi-agent core)

These five are NOT in the curriculum. They are what differentiates this
from a class project.

| Layer | File | What it does |
| --- | --- | --- |
| Image safety gate | `src/utils/safe_image.py` | preflight (suffix, size, resolution) + auto-resize to 1024 px before the pipeline ever sees the file |
| LangChain `@tool` pre-tools | `src/agents/tools.py` | k-means palette, OpenCV text-size, CTA-density, Δ-E palette distance — run BEFORE the LLM, ground its prompt |
| Anti-hallucination prompt scaffolding | `src/utils/prompts/_shared.py` | `ANTI_HALLUCINATION_RULE` + `ABSTENTION_RULE` templated into every system prompt; pinned by regression tests |
| Cost tracker + circuit breaker | `src/llm/cost_tracker.py` | per-run telemetry visible in Settings; fast-fail after 2 hard failures so a typo'd API key cannot burn 25 doomed calls |
| Quality gate + 1-shot synthesizer retry | `src/agents/quality_gate.py` | pure-Python content checks; if a `fail`-severity issue is found in the first synthesizer output, ONE corrective re-prompt is sent |

## Dependency injection seam

```mermaid
flowchart LR
    subgraph contracts [src/contracts.py — Protocols]
        P1["LLMClient.complete(messages, schema) -> BaseModel"]
        P2["VisionLLM.analyze(image, prompt, schema) -> BaseModel"]
        P3["Retriever.retrieve(query, k) -> list[RetrievedRef]"]
        P4["WebSearch.search(query, k) -> list[SearchResult]"]
    end

    subgraph real [Real implementations]
        R1[OpenRouterClient]
        R2[OpenRouterVision]
        R3[LanceRetriever]
        R4[TavilySearch / DuckDuckGoSearch]
    end

    subgraph fakes [src/fakes — Deterministic doubles]
        F1[FakeLLM]
        F2[FakeVisionLLM]
        F3[FakeRetriever]
        F4[FakeSearch]
    end

    R1 -- implements --> P1
    R2 -- implements --> P2
    R3 -- implements --> P3
    R4 -- implements --> P4
    F1 -- implements --> P1
    F2 -- implements --> P2
    F3 -- implements --> P3
    F4 -- implements --> P4

    P1 --> AgentDeps[AgentDeps container]
    P2 --> AgentDeps
    P3 --> AgentDeps
    P4 --> AgentDeps
    AgentDeps --> Agents[All agent nodes]
```

## Data flow on one click of "Run"

1. **UI** receives `image_path` + `instructions` and validates the upload
   via `src.utils.safe_image.preflight_image`. Bad files are rejected with
   a clean banner; oversized images are auto-resized to 1024 px.
2. **`run_graph`** builds `AgentDeps` (real or fake), constructs `GraphState`,
   and resets the `CostTracker`.
3. **Per-agent pre-tools** run synchronously before the LLM call:
   `extract_palette` for visual, `estimate_text_size` for accessibility,
   `cta_density` for ux, `palette_distance` for brand. Their outputs are
   injected into the user prompt as `<measured_facts>` so the model never
   has to invent them.
4. **Fan-out from `START`**: `visual`, `ux`, `accessibility`, `brand`,
   `market` execute concurrently via LangGraph's `asyncio.gather` scheduler.
   Each returns a partial-state dict — no write conflicts.
5. **Synthesizer** consumes the merged state, calls the LLM with
   `schema=DesignReport`, and runs the quality gate. If a `fail`-severity
   issue is found in the first output, a single corrective re-prompt is
   sent with the failure list.
6. **Persistence**: report JSON saved to `data/reports/<ts>-<stem>.json`;
   cost ledger snapshotted for the Settings tab.
7. **UI** renders the premium report (Tab 1), the references the agents
   actually consulted (Tab 2), and the cost / tools telemetry (Tab 3).
   Any unexpected exception is converted to a friendly banner via
   `ui.handlers._classify_run_error` — the user never sees a Python
   traceback.

## UI module split

```
ui/
  app.py          # entry point + Blocks layout + main()
  state.py       # settings refresh, status / settings cards, telemetry
  handlers.py    # on_run + classify_run_error (graceful errors)
  render.py      # premium DesignReport HTML rendering
  references.py  # References-tab payload + ad-hoc search handler
  styles.py      # loads APP_CSS + light-theme JS / HEAD HTML
  static/app.css # actual CSS (real .css file, not Python string)
```

The split exists to keep every Python file under 500 LOC. `python -m
ui.app` and the HF Spaces `app.py` shim both still resolve to the same
entry point.

## Extension points (post-MVP)

- **Hybrid retrieval** — combine CLIP image vectors with text-keyword filter.
- **LLM-as-judge in evals** — replace `schema_valid` with a rubric score.
- **Tier selection** — `cost.select_model` becomes a real router that picks
  cheaper models for narrow tasks and bigger ones for brand consistency.
- **Multi-tenant LanceDB** — add `tenant_id` to the schema.
- **Async MCP transport** — swap stdio for HTTP behind a reverse proxy.
- **Tile mode for huge screenshots** — split a 6 K x 4 K capture into
  quadrants, run the visual agent on each, then a final pass to reason
  across tiles. Already designed; one config switch and a Python loop.
