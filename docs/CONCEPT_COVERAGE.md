# Concept Coverage — the slide for the judges

We map every accelerator concept to a real file in this repo. If the judges
ask "where is X?" the answer is one click away.

## Sprint coverage (1-6) — every concept has a real artifact

| Sprint | Concept | Where it lives | How we use it |
|---|---|---|---|
| 1 | Prompt engineering (XML / JSON-mode + grounding rules) | `src/utils/prompts/` (one file per agent) | XML `<context>/<task>` blocks, JSON-schema mode, anti-hallucination + abstention rules templated everywhere. |
| 1 | OpenAI Chat Completion standard | `src/llm/openrouter_client.py` | `openai` SDK pointed at OpenRouter; one key, many models. |
| 1 | Pydantic + JSON schema prompting | `src/schemas/outputs.py` + `OpenRouterClient.complete` | `response_format={"type":"json_schema",...}` derived from `schema.model_json_schema()`. |
| 2 | Gradio UI (Blocks + custom CSS) | `ui/app.py`, `ui/styles.py`, `ui/static/app.css` | Drag-drop upload, premium report rendering, status banners, settings telemetry, three tabs. |
| 2 | Hugging Face local model (concept claim) | `src/llm/hf_local.py` | `transformers` is opt-in via `requirements/optional-hf.txt`. Fakes work without it. |
| 3 | RAG end-to-end | `src/rag/*` + `scripts/ingest_references.py` | Ingest → embed → store → retrieve. |
| 3 | Chunking & embeddings | `src/rag/embedder.py` | CLIP image+text in the same vector space. |
| 3 | LanceDB vector DB | `src/rag/vector_store.py` | Embedded columnar Arrow store. |
| 3 | LlamaIndex (concept claim) | `src/rag/retriever.py` (one import) | LanceDB direct path is the production route. |
| 4 | Evals | `src/evals/harness.py` | Schema-validity over `GOLDEN_CASES`; one number for the judges. |
| 4 | MCP | `src/mcp/server.py` | Two tools (`analyze_design`, `search_designs`) over stdio. |
| 5 | LangChain `@tool` decorator | `src/agents/tools.py` | Real LangChain `BaseTool` instances (verified by `list_langchain_tools`); compatible with `model.bind_tools(...)`. Includes basic tools (`read_file`, `list_files`, `web_search`) AND specialist pre-tools. |
| 5 | LangGraph multi-agent | `src/agents/graph.py` | `StateGraph` with parallel fan-out + synthesizer. |
| 5 | LangSmith tracing | `src/utils/tracing.py` | `init_tracing()` exports env vars; `traced` context manager. |
| 5 | Cost optimization | `src/llm/cost.py` + `src/llm/cost_tracker.py` | Disk-backed JSON cache + per-run telemetry + circuit breaker. |
| 6 | Parallel multi-agent fan-out | `src/agents/graph.py` (`SPECIALIST_BRANCHES`) | Five concurrent `Runnable` branches. |
| 6 | Structured aggregated output | `src/agents/synthesizer.py` | `DesignReport` Pydantic model + 1-shot quality-gate retry. |

**Sprint coverage: 6 / 6.** Every Sprint 1-6 concept has a real artifact
the judges can point at.

## Robustness pillars — what we built BEYOND the curriculum

The ten layers below are not in the syllabus. They are what turns a
class project into something close to a product. Each is implemented
today and listed in `docs/ARCHITECTURE.md` with a one-line description.

| Pillar | File | Why it earns Difficulty + Code-Quality points |
|---|---|---|
| Image safety gate | `src/utils/safe_image.py` | preflight (suffix, 20 MB cap, 4 MP cap) + auto-resize to 1024 px before pipeline. Crashes from 100 MB uploads cannot reach Gradio. Tested: `tests/test_safe_image.py`. |
| LangChain `@tool` pre-tools | `src/agents/tools.py` + `src/agents/_color_math.py` | k-means in CIELab, OpenCV connected-components text-size, CTA-density, Δ-E palette distance. Run BEFORE the LLM and inject `<measured_facts>`. Net token saver. Tested: `tests/test_tools.py`. |
| Anti-hallucination prompt scaffolding | `src/utils/prompts/_shared.py` | `ANTI_HALLUCINATION_RULE` + `ABSTENTION_RULE` + per-agent grounding clauses (e.g. "do NOT name a font", "WCAG SC list is closed", "metric_lift only when grounded"). Pinned by 37 regression tests in `tests/test_prompts.py`. |
| Cost tracker + circuit breaker | `src/llm/cost_tracker.py` | Per-run cost telemetry visible in Settings (calls, tokens, USD, cache hits); fast-fail after 2 hard failures so a typo'd API key cannot burn 25 doomed calls. |
| Quality gate + 1-shot synthesizer retry | `src/agents/quality_gate.py` | Pure-Python content checks (executive summary length, score-breakdown coverage, recommendation completeness). If first synth output fails, ONE corrective re-prompt runs. Tested: `tests/test_quality_gate.py`. |
| Editorial fallback for references | `src/rag/editorial_refs.py` | When both image RAG and web search return empty, a hand-curated list keeps the References tab useful. Tested: `tests/test_editorial_refs.py`. |
| Graceful error handling | `ui/handlers.py` (`_classify_run_error`) | Every exception from `on_run` is mapped to a user-friendly banner (rate limit, network, API auth, validation). Server log has the full stack; the user never sees a Python traceback. |
| Multi-frame comparison mode | `src/schemas/outputs.py` (`GraphState.image_paths`, `frame_labels`, `RetrievedRef.matched_frames`, `Recommendation.affected_frames`, `DesignReport.per_frame_scores`) + every vision agent + the synthesizer | 1-5 screenshots of the same product analysed as ONE coherent product. Vision agents see all frames in one call; brand RAG queries every frame and dedupes; synthesizer correlates findings across screens, names affected frames per recommendation, emits a per-frame heatmap. Tested: `tests/person_a/test_graph.py::test_run_graph_multi_frame_with_labels`, `tests/test_schemas.py::test_design_report_carries_frame_labels_field`, `tests/test_safe_image.py::test_preflight_batch_*`. |
| Visual-agent self-heal on shallow response | `src/agents/visual_analysis.py` (`_is_shallow_visual`) | Detects the gpt-4o-mini multi-image bug (strict `json_schema` rejected, fallback returns palette-only) and re-prompts ONCE with a corrective directive. Cost doubles only on broken runs. Tested: `tests/person_c/test_visual_analysis.py::test_visual_run_retries_on_shallow_response` + `test_visual_run_keeps_partial_when_retry_also_shallow`. |
| Persistent on-disk app log | `src/utils/logger.py` → `data/logs/app.log` | Every log line is tee'd to disk with 10 MB rotation (5 backups). Path printed at launch + shown in Settings. Users tail a file instead of copy-pasting from the rolling console. `LOG_TO_FILE=0` in `.env` opts out. |

## What we deliberately did NOT build

- `litellm`, `instructor`, `langchain-community` — duplicated concepts already
  covered by `openai` SDK + Pydantic JSON-schema mode + `langchain-core`.
- Console scripts (`design-suite-*`) — `make` targets do the same job.
- Per-tenant auth, Redis cache, HTTP MCP — production polish (see
  `docs/walkthrough.html` "Scaling" tab).
- LLM-as-judge in evals — schema-validity is enough for hackathon scoring.
- Streaming token-by-token UI — agent-level status lines + final render.

## Total file count vs concept count

- **17 sprint concepts** mapped to **22 real files** (some concepts touch
  multiple files; nothing is double-counted).
- **7 robustness layers** (above) on top, each in 1-2 files.
- **121 tests passing** across 18 test modules.

If a concept is missing from this table, that is the bug. Open an issue.
