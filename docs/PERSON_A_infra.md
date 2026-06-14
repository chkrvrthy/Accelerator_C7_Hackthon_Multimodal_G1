# Person A — Infra and Orchestration

> **Mission.** You own the seams and the orchestrator. If two people disagree
> on a type, you arbitrate. After Hour 1 your contracts are frozen — anyone
> wanting to change them files a 2-line PR rationale.

## Why your slice exists (concepts you are demonstrating)

| Sprint | Concept | What you ship |
|---|---|---|
| 1 | Pydantic v2 + JSON-schema prompting | `src/schemas/outputs.py`, `src/llm/openrouter_client.py` |
| 5 | LangGraph multi-agent state machine | `src/agents/graph.py` |
| 5 | LangSmith tracing | `src/utils/tracing.py` |
| 5 | Cost optimization (cache + tier stub) | `src/llm/cost.py` |
| 6 | Parallel multi-agent fan-out + structured aggregation | `src/agents/graph.py`, `src/agents/synthesizer.py` |

You also ship the *infrastructure for Code Quality (10/10)*: dependency injection
via Protocols, fakes for offline development, and the cross-cutting test suite.

## Files you own

| File | One-line purpose |
|---|---|
| `src/schemas/outputs.py` | Pydantic models for every cross-module data shape. |
| `src/contracts.py` | Protocol classes — the seams between people. |
| `src/fakes/*` | Deterministic doubles for every Protocol. |
| `src/llm/openrouter_client.py` | Real `LLMClient` over OpenRouter — wired to cost-tracker + circuit-breaker. |
| `src/llm/multimodal.py` | Real `VisionLLM`. |
| `src/llm/cost.py` | Disk-backed response cache + `@cached` decorator. |
| `src/llm/cost_tracker.py` | Process-wide cost telemetry + circuit breaker. |
| `src/llm/hf_local.py` | Sprint 2 HF concept stub. |
| `src/agents/base.py` | `AgentDeps` container + `run_with_schema` helper. |
| `src/agents/synthesizer.py` | Aggregate specialists → `DesignReport` + 1-shot quality-gate retry. |
| `src/agents/graph.py` | LangGraph wiring + plain-Python fallback. |
| `src/agents/quality_gate.py` | Pure-Python content checks for `DesignReport`. |
| `src/agents/tools.py` | LangChain `@tool` registry — pre-tools + basic tools. |
| `src/agents/_color_math.py` | CIELab / k-means helpers used by `tools.py`. |
| `src/utils/tracing.py` | LangSmith init + `traced` context manager. |
| `src/utils/safe_image.py` | Upload preflight + auto-resize. |
| `src/evals/*` | Schema-validity eval harness. |
| `tests/conftest.py`, `tests/test_{schemas,contracts,fakes,prompts,tools,safe_image,quality_gate}.py`, `tests/person_a/*` | Cross-cutting + your slice tests. |

## Architecture view

See `docs/ARCHITECTURE.md` ("Person A — Infra and Orchestration" diagram) and
`docs/walkthrough.html` for the interactive version.

## Contracts you must keep stable (frozen after Hour 1)

```python
class LLMClient(Protocol):
    def complete(self, *, system, user, schema, model=None, temperature=None) -> BaseModel: ...

class VisionLLM(Protocol):
    # ``images`` accepts 1..5 paths; agents pass ``state.image_paths`` whole.
    def analyze(self, *, system, user, images, schema, model=None) -> BaseModel: ...

class Retriever(Protocol):
    def retrieve_by_image(self, image_path, k=5) -> list[RetrievedRef]: ...
    def retrieve_by_text(self, text, k=5) -> list[RetrievedRef]: ...

class WebSearch(Protocol):
    def search(self, query, k=5) -> list[SearchResult]: ...
```

### Multi-frame fields you own (Hour 2 additions, additive only)

| Field | Where | Default for legacy callers |
| --- | --- | --- |
| `GraphState.image_paths: list[str]` | every agent input | populated from `image_path` by validator |
| `GraphState.frame_labels: list[str]` | every agent input | filename stems via validator |
| `RetrievedRef.matched_frames: list[str]` | brand RAG output | `[]` for single-frame |
| `Recommendation.affected_frames: list[str]` | every recommendation | `[]` for single-frame |
| `DesignReport.frame_labels: list[str]` | report root | `[]` for single-frame |
| `DesignReport.per_frame_scores: dict[str, dict[str, float]]` | report root | `{}` for single-frame |

These are all **additive** — nothing breaks for existing single-image callers because every default is empty. The synthesizer scrubs hallucinated frame labels server-side against the canonical set.

If you need to change one of these:
1. Open a 2-line PR rationale.
2. Update the matching fake in `src/fakes/`.
3. Run `make test` — every slice's tests must still pass.

## Setup — first 5 minutes (do exactly this)

### 1. Clone and create a venv

**Linux / macOS:**

```bash
git clone <repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-a-infra.txt
```

**Windows (PowerShell):**

```powershell
git clone <repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-a-infra.txt
```

> If `make` is not available on Windows, see the README "Quickstart" — every
> `make <target>` maps to a single `python -m ...` command in the Makefile.

### 2. Get keys (Person A signs up for ALL of them — you arbitrate the wiring)

| Key | Mandatory for Person A? | Where to get it | Free tier? |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** | https://openrouter.ai/keys (Sign in → "Create Key") | Pay-as-you-go; add $5 credit, lasts the whole hackathon |
| `LANGCHAIN_API_KEY` | Recommended | https://smith.langchain.com/settings → "API Keys" | Yes — 5,000 traces/month |
| `TAVILY_API_KEY` | No (Person E owns) | https://app.tavily.com/home → "API Keys" | Yes — 1,000 queries/month |

### 3. Copy and fill `.env`

```bash
# Linux / macOS:
cp .env.example .env

# Windows (PowerShell):
Copy-Item .env.example .env
```

**File to edit:** `./.env` (the file you just created at the repo root — NOT
`.env.example`, that's the template). Open it in your editor.

Make exactly **four edits** — find each "before" line and replace it with
the "after" line. Line numbers reference `.env.example` so you can locate
them quickly.

| Line | Before (find this) | After (replace with) |
|---|---|---|
| L10 | `OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME` | `OPENROUTER_API_KEY=sk-or-v1-<paste your key>` |
| L49 | `LANGCHAIN_TRACING_V2=false` | `LANGCHAIN_TRACING_V2=true` |
| L50 | `LANGCHAIN_API_KEY=` | `LANGCHAIN_API_KEY=lsv2_pt_<paste your key>` |
| L65 | `USE_REAL=0` | `USE_REAL=1` |

Leave every other line as-is. Person E will fill `TAVILY_API_KEY` (L28) on
their own machine — that one is theirs.

**Never commit `.env`.** It's already in `.gitignore`. Only `.env.example`
ships in git.

### 4. Verify your env loaded

```bash
python -c "from src.config import settings; print('key set:', bool(settings.openrouter_api_key)); print('tracing:', settings.langchain_tracing_v2)"
# Expect: key set: True   tracing: True
```

If you see `key set: False`, your shell is in a different cwd than `.env` — `cd` into the repo root before running.

### 5. First successful run

```bash
make test-a            # 56 tests pass against fakes — no keys needed
make run-a             # full graph against the bundled sample image (fakes)
USE_REAL=1 make run-a  # full graph against OpenRouter — costs ~$0.005
```

If step 5 fails, check the very first ERROR line in the log — `run_with_schema` always names the failing agent and the underlying error type. See `docs/FAQ.md` § 6 for the debug story.

## Run-in-isolation

```
make run-a                              # python -m src.agents.graph --image src/fakes/fixtures/sample.png
USE_REAL=1 make run-a                   # full graph against a real API
python -m src.llm.openrouter_client --smoke   # round-trip a tiny JSON-mode call
```

## Smoke tests

```
make test-a                # your slice + cross-cutting (schemas/contracts/fakes)
make test-real             # real_api tests — requires OPENROUTER_API_KEY
make cov                   # coverage across src/
```

## Implementation hot-spots (where to start)

1. **`src/llm/openrouter_client.py:complete`** — wire `chat.completions.create`
   with `response_format={"type":"json_schema",...}` derived from
   `schema.model_json_schema()`. Validate, return `schema(**parsed)`.
2. **`src/llm/multimodal.py:OpenRouterVision.analyze`** — resize images to
   max-side 1024, encode as data URIs, build the `messages` payload, delegate
   to the text client with `response_format`.
3. **`src/llm/cost.py:cached`** — wrap `complete` and `analyze`. Hash inputs
   via `prompt_hash`, look up `ResponseCache.get`, write through on miss.
4. **`src/agents/graph.py:build_graph`** — replace the closure-wrapped
   `add_node` with proper async wrappers and `compiled.ainvoke(...)`.
5. **`src/utils/tracing.py:traced`** — push an explicit run via the `langsmith`
   SDK so non-LangChain code (e.g. `LanceRetriever`) shows up as a span too.

## Done when

- [ ] `make test-a` is green from a fresh `.venv`.
- [ ] `make run-a` produces a valid `DesignReport` JSON under `data/reports/`.
- [ ] LangSmith UI shows 6 spans when key is set; logs locally otherwise.
- [ ] `mypy src/` is clean.

## Hand-off contract

After Hour 1, contracts are frozen. Any change requires a 2-line PR description
including the fake update.

## Common pitfalls

- **JSON mode quirks** — some OpenRouter providers reject strict JSON schema.
  Fallback: `response_format={"type":"json_object"}` + manual `model_validate`.
- **LangGraph state mutation** — return a *partial* dict from each node; never
  mutate the input `state` in place.
- **LangSmith env var loading order** — call `init_tracing()` BEFORE building
  the graph; the env vars are read by LangChain at first `Runnable` construction.
