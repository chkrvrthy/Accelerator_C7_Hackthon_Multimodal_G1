# Architecture

This is the single page the demo MC reads aloud. The interactive version is
`docs/walkthrough.html` — open it in any browser, no build step required.

## Big picture

```mermaid
flowchart TB
    User[User] --> UI[Gradio UI<br/>ui/app.py]
    UI --> Orchestrator[LangGraph Orchestrator<br/>src/agents/graph.py]

    subgraph rag [Image RAG layer]
        Embed[CLIP Embedder<br/>src/rag/embedder.py]
        VStore[LanceDB Store<br/>src/rag/vector_store.py]
        Retr[Retriever<br/>src/rag/retriever.py]
        Embed --> VStore --> Retr
    end

    subgraph agents [LangGraph Specialist Agents]
        VA[Visual Analysis Agent]
        UX[UX Critique Agent]
        MR[Market Research Agent]
        AC[Accessibility Agent]
        BR[Brand Consistency Agent]
        SY[Synthesizer Agent]
    end

    Orchestrator --> VA
    Orchestrator --> UX
    Orchestrator --> MR
    Orchestrator --> AC
    Orchestrator --> BR
    VA --> SY
    UX --> SY
    MR --> SY
    AC --> SY
    BR --> SY
    SY --> Orchestrator

    BR -.uses.-> Retr
    MR -.uses.-> WebSearch[Tavily / DuckDuckGo<br/>src/tools/web_search.py]
    VA -.uses.-> LLM[Multimodal LLM<br/>src/llm/multimodal.py]
    UX -.uses.-> LLM
    AC -.uses.-> LLM

    LLM --> OR[OpenRouter Gateway<br/>src/llm/openrouter_client.py]
    OR --> Cache[Cost Optimizer<br/>cache + model tiering<br/>src/llm/cost.py]

    Orchestrator -.traces.-> LS[LangSmith]
    Orchestrator --> Report[Final JSON Report<br/>data/reports/*.json]
    Report --> UI

    MCP[MCP Server<br/>src/mcp/server.py] -.exposes tools to.-> ExternalAgent[External Agents<br/>Claude Code, MCP clients]
    MCP -.calls.-> Orchestrator
```

## Dependency injection seam

```mermaid
flowchart LR
    subgraph contracts [src/contracts.py - Protocols]
        P1["LLMClient.complete(messages, schema) -> BaseModel"]
        P2["VisionLLM.analyze(image, prompt, schema) -> BaseModel"]
        P3["Retriever.retrieve(query, k) -> list[RetrievedRef]"]
        P4["WebSearch.search(query, k) -> list[SearchResult]"]
    end

    subgraph real [Real implementations]
        R1[OpenRouterClient]
        R2[OpenRouterVision]
        R3[LanceRetriever]
        R4[TavilySearch]
    end

    subgraph fakes [src/fakes - Deterministic doubles]
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

1. **UI** receives `image_path` + `instructions`.
2. **`run_graph`** builds `AgentDeps` (real or fake), constructs `GraphState`.
3. **Fan-out from `START`**: `visual`, `ux`, `accessibility`, `brand`, `market`
   all execute concurrently via LangGraph's `asyncio.gather` scheduler.
   Each returns a partial-state dict — no write conflicts.
4. **Synthesizer** consumes the merged state, calls the LLM with
   `schema=DesignReport`, persists the JSON to `data/reports/<ts>-<stem>.json`.
5. **UI** renders the report (Tab 2) with the retrieved references gallery
   (Tab 3 of the same run).

## Extension points (post-MVP)

- **Hybrid retrieval** — combine CLIP image vectors with text-keyword filter.
- **LLM-as-judge in evals** — replace `schema_valid` with a rubric score.
- **Tier selection** — `cost.select_model` becomes a real router that picks
  cheaper models for narrow tasks (e.g. accessibility) and bigger ones for
  brand consistency.
- **Multi-tenant LanceDB** — add `tenant_id` to the schema.
- **Async MCP transport** — swap stdio for HTTP behind a reverse proxy.
