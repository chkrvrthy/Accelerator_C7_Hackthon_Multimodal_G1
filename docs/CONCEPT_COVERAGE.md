# Concept Coverage — the slide for the judges

We map every accelerator concept to a real file in this repo. If the judges
ask "where is X?" the answer is one click away.

| Sprint | Concept | Where it lives | How we use it |
|---|---|---|---|
| 1 | Prompt engineering (XML/JSON-mode) | `src/utils/prompts.py`, `src/agents/ux_critique.py` (XML tags) | Every system prompt + `<context>/<task>` blocks. |
| 1 | OpenAI Chat Completion standard | `src/llm/openrouter_client.py` | `openai` SDK pointed at OpenRouter; one key, many models. |
| 1 | Pydantic + JSON schema prompting | `src/schemas/outputs.py` + `OpenRouterClient.complete` | `response_format={"type":"json_schema",...}` derived from `schema.model_json_schema()`. |
| 2 | Gradio UI | `ui/app.py` | Drag-drop, streaming logs, structured tabs. |
| 2 | HuggingFace local model | `src/llm/hf_local.py` | Concept-claim stub; `transformers` is opt-in via `requirements/optional-hf.txt`. |
| 3 | RAG end-to-end | `src/rag/*` + `scripts/ingest_references.py` | Ingest → embed → store → retrieve. |
| 3 | Chunking & embeddings | `src/rag/embedder.py` | CLIP image+text in the same vector space. |
| 3 | LanceDB vector DB | `src/rag/vector_store.py` | Embedded columnar Arrow store. |
| 3 | LlamaIndex | `src/rag/retriever.py` (single import) | Concept claim; LanceDB direct path is the production route. |
| 4 | Evals | `src/evals/harness.py` | Schema-validity over `GOLDEN_CASES`; one number for the judges. |
| 4 | MCP | `src/mcp/server.py` | Two tools (`analyze_design`, `search_designs`) over stdio. |
| 5 | LangChain tools | `src/tools/rag_tool.py` | BaseTool wrapper around the `Retriever` Protocol. |
| 5 | LangGraph multi-agent | `src/agents/graph.py` | StateGraph with parallel fan-out + synthesizer. |
| 5 | LangSmith tracing | `src/utils/tracing.py` | `init_tracing()` exports env vars; `traced` context manager. |
| 5 | Cost optimization | `src/llm/cost.py` | Disk-backed JSON cache + `select_model` stub. |
| 6 | Parallel multi-agent fan-out | `src/agents/graph.py` (`SPECIALIST_BRANCHES`) | Five concurrent `Runnable` branches. |
| 6 | Structured aggregated output | `src/agents/synthesizer.py` | `DesignReport` Pydantic model. |

**Sprint coverage: 6/6.** Nothing was lost in the cuts.

## What we deliberately did NOT build

- `litellm`, `instructor`, `langchain-community` — duplicated concepts.
- Pre-commit hooks — out of hackathon scope.
- Console scripts (`design-suite-*`) — `make` targets do the same job.
- Per-tenant auth, Redis cache, HTTP MCP — production polish (see
  `docs/walkthrough.html` "Scaling" tab).
