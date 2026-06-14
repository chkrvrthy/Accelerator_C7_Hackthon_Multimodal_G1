# Person C — Visual + Brand Consistency Agents

> **Mission.** You see what the screen shows. Your visual + brand outputs feed
> the synthesizer. Two agents, two schemas, one mental model: pull from the
> Protocol container, return a partial-state dict.

## Why your slice exists (concepts you are demonstrating)

| Sprint | Concept | What you ship |
|---|---|---|
| 1 | Multimodal prompt + JSON-schema output | `src/agents/visual_analysis.py` |
| 3 | RAG end-to-end (the only agent that consumes the retriever) | `src/agents/brand_consistency.py` |
| 6 | Two parallel branches of the multi-agent fan-out | both files above |

The brand-consistency agent is the *only* one that exercises Image RAG end-to-end
during a normal demo run. Treat it as the highest-value path.

## Files you own

| File | One-line purpose |
|---|---|
| `src/agents/visual_analysis.py` | `run(state, deps)` → `{"visual": VisualAnalysis}`; runs `extract_palette` pre-tool first. |
| `src/agents/brand_consistency.py` | `run(state, deps)` → `{"brand": BrandConsistency}`; runs `palette_distance` pre-tool. |
| `src/utils/prompts/visual.py` | Visual system + user prompts (LRU-cached, anti-hallucination rules baked in). |
| `src/utils/prompts/brand.py` | Brand system + user prompts. |
| `src/schemas/outputs.py` (your two output models) | `VisualAnalysis`, `BrandConsistency`. |
| `tests/person_c/*` | Your test slice. |

## Contracts you consume (from `src/contracts.py`)

```python
class VisionLLM(Protocol):
    # ``images`` accepts 1..5 paths — pass state.image_paths whole.
    def analyze(self, *, system, user, images, schema, model=None) -> BaseModel: ...

class Retriever(Protocol):     # used by brand_consistency only
    def retrieve_by_image(self, image_path, k=5) -> list[RetrievedRef]: ...
```

You receive these wrapped in an `AgentDeps` (see `src/agents/base.py`). Never
import a concrete class.

### Multi-frame contract (already wired — what to remember when iterating)

- **Visual agent**: pass every uploaded frame in one call —
  `images=[Path(p) for p in state.image_paths]`. Append
  `multi_image_note(len(state.image_paths), state.frame_labels)` to the
  user message so the LLM cites findings by frame label, not by index.
- **Brand agent**: `_retrieve_for_all_frames` runs CLIP retrieval once
  per frame, dedupes by ref id (highest score wins), and stamps
  `matched_frames` on each kept ref. The user prompt's
  `<retrieved_refs>` block exposes `matched_frames` so the LLM can
  attribute drift findings to specific screens.
- **Recommendation contract**: every recommendation the synthesizer
  generates from your output should populate `affected_frames` on
  multi-frame runs. You do not write these directly — your job is to
  emit findings with frame-attributed evidence in the description so
  the synthesizer has signal to fill the field.

## Setup — first 5 minutes (do exactly this)

### 1. Clone and create a venv

**Linux / macOS:**

```bash
git clone <repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-c-agents.txt
```

**Windows (PowerShell):**

```powershell
git clone <repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-c-agents.txt
```

### 2. Keys you need

| Key | Mandatory for Person C? | Where to get it | Free tier? |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** for `USE_REAL=1` runs (the whole point — real vision LLM scoring real designs) | https://openrouter.ai/keys | Pay-as-you-go (add $5; lasts the hackathon) |

You can do **80% of your work without any key** — `make test-c` runs your agents through the `FakeVisionLLM` and validates schemas. You only need a real key when you start iterating on prompts ("does the LLM actually return proper hex codes?").

### 3. Copy and fill `.env`

```bash
# Linux / macOS:
cp .env.example .env

# Windows (PowerShell):
Copy-Item .env.example .env
```

**File to edit:** `./.env` (the file you just created at the repo root — NOT
`.env.example`, that's the template). Open it in your editor.

Make exactly **two edits** — find each "before" line and replace it with
the "after" line. Line numbers reference `.env.example`.

| Line | Before (find this) | After (replace with) |
|---|---|---|
| L10 | `OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME` | `OPENROUTER_API_KEY=sk-or-v1-<paste your key>` |
| L65 | `USE_REAL=0` | `USE_REAL=1` |

Leave every other line as-is. The other persons own their own keys
(LangSmith → Person A, Tavily → Person E); you don't need to touch them.

**Never commit `.env`.** It's already in `.gitignore`. Only `.env.example`
ships in git.

### 4. Verify your env loaded

```bash
python -c "from src.config import settings; print('key set:', bool(settings.openrouter_api_key)); print('use_real:', settings.use_real)"
# Expect: key set: True   use_real: True
```

### 5. First successful run

```bash
make test-c                                        # offline (fakes) — should be green
make run-c-visual                                  # against fakes
USE_REAL=1 make run-c-visual                       # against real OpenRouter — costs ~$0.001 per call
USE_REAL=1 make run-c-brand                        # uses Person B's retriever (FakeRetriever if no LanceDB)
```

If `make run-c-brand` reports "no references retrieved", that's expected before Person B ingests a real corpus — the agent has a graceful fallback path with a clear log message ("score is an estimate"). See `src/agents/brand_consistency.py`.

## Run-in-isolation

```
make run-c-visual                              # uses fakes — no key required
make run-c-brand
USE_REAL=1 OPENROUTER_API_KEY=... make run-c-visual    # real LLM
```

Each agent has a `__main__` so you can iterate without touching anyone else's
files.

## Smoke tests

```
make test-c
```

## Implementation hot-spots

1. **`visual_analysis.run`** — already wired against `run_with_schema`. Your
   work is in `utils/prompts.visual_analysis_system()` — refine the prompt
   so the palette comes back as proper hex codes.
2. **`brand_consistency.run`** — replace the placeholder ``images`` list with
   a side-by-side composite via `tools.image_utils.side_by_side(...)` (Person
   B's helper). Pass the composite + ref scores in the user text.
3. **`schemas.outputs.VisualAnalysis._strip_blanks`** — once palette is stable
   hex, tighten the validator to require `^#[0-9A-Fa-f]{6}$`.

## Done when

- [ ] `make test-c` is green from a fresh `.venv`.
- [ ] With `USE_REAL=1` and a real key, both agents produce non-empty findings
      against a real screenshot.
- [ ] Brand agent gracefully handles `refs == []` (corpus empty) — see test
      `test_brand_run_no_refs_fallback`.

## Common pitfalls

- **LLM emitting markdown around JSON** — your prompt's "OUTPUT RULES" section
  must say "no markdown, no code fences" verbatim.
- **Forgetting the side-by-side composite** — sending 5 separate `image_url`
  parts is 5× more tokens than 1 composite.
- **Palette not validated as hex** — once the validator tightens, hallucinated
  values like "navy" will fail validation and break the whole graph. Catch it
  in your prompt iterations, not at runtime.

## Self-heal loop on shallow responses (read this before tuning the prompt)

`gpt-4o-mini` rejected strict `json_schema` on multi-image runs about
95% of the time, which is why we switched the project default to
`openai/gpt-5-mini` in June 2026 (rejection rate <5%). The
self-heal mechanism still ships because (a) some users override
`DEFAULT_VISION_MODEL` to a cheaper model like `gpt-5-nano` or
`gpt-4o-mini` for cost reasons, and (b) any future model with the
same `json_schema` quirk gets handled automatically.

When a rejection does happen, the fallback to `json_object` is loose
— the model can skip every string field because they all default to
`""`. The result: a "successful" call that returns only
`{"palette": [...]}` and an empty narrative.

The agent self-heals via `_is_shallow_visual` (in
`src/agents/visual_analysis.py`). If 3+ narrative strings come back
empty AND `observations` is empty, the agent re-prompts ONCE with a
sharp critique and replaces the partial response if the retry
recovers. You will see this in the log as:

```
WARNING agent.visual: shallow response (palette-only).
        Retrying once with a corrective directive.
INFO    agent.visual: retry recovered the narrative.
```

Cost discipline:
- Clean runs pay nothing extra.
- Broken runs pay 2× for the visual call only (other agents unaffected).
- The retry uses the same model — escalating to a stronger one is a
  config change, not a code path. If the failure rate stays high
  even after the retry, switch `DEFAULT_VISION_MODEL` to
  `openai/gpt-4o` or `anthropic/claude-3.5-sonnet` in `src/config.py`.

When you tune `utils/prompts/visual.py`, keep the **FORBIDDEN OUTPUTS**
section. It is what teaches the model that palette-only is not an
acceptable response. Removing it brings the failure rate back to ~95%.

Tests that lock this behavior:
- `test_is_shallow_visual_detector` — pin the detector heuristic.
- `test_visual_run_retries_on_shallow_response` — the recovery loop.
- `test_visual_run_keeps_partial_when_retry_also_shallow` — bound the
  retry budget to exactly one extra call (no infinite loops).
- **Severity inflation** — every Finding marked `critical` is meaningless.
  Anchor severity to a small rubric in the prompt.
