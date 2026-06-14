# Cost discipline

> Where this project spends tokens, what stops it from spending too many, and the math for a typical run.

This document is the single page to read if you're worried about the bill. Every guardrail listed here is wired in code today; nothing below is aspirational.

---

## 1. Default model choice

| Knob | Value | Why |
| --- | --- | --- |
| `default_text_model` | `openai/gpt-4o-mini` | $0.15/Mtok in, $0.60/Mtok out — ~10× cheaper than Sonnet |
| `default_vision_model` | `openai/gpt-4o-mini` | Vision-capable mini covers the hackathon use case |
| `default_temperature` | `0.2` | Low temperature → JSON adherence is reliable AND cache hit-rate is high |
| `default_max_tokens` | `2,048` | Hard cap per call so a chatty model can't run away |

Override anything in `.env`. The `OPENROUTER_*` envs flow through `pydantic-settings` into `Settings`; nothing else reads `os.environ`.

## 2. The seven token-burn entry points and their guardrails

```
┌────────────────────────────────────────────────────────────────┐
│  1. visual agent          system 1.1 kT + image ~700 tok       │
│  2. ux agent              system 1.2 kT + image ~700 tok       │
│  3. accessibility agent   system 1.0 kT + image ~700 tok       │
│  4. brand agent           system 1.1 kT + image ~700 tok       │
│  5. market agent          system 1.0 kT (text only)            │
│  6. synthesizer agent     system 2.4 kT + 5 spec outputs ~2 kT │
│  7. UI on-page LLM hits   none — all text in UI is static      │
└────────────────────────────────────────────────────────────────┘
                            ▼
                ┌──────────────────────┐
                │  Disk-backed cache   │   ← same prompt + image hash
                │  ~/data/cache/*.json │     returns instantly, free
                └──────────────────────┘
                            ▼
                ┌──────────────────────┐
                │   Cost tracker       │   ← logs every call,
                │   src/llm/cost_…     │     surfaces in Settings tab
                └──────────────────────┘
                            ▼
                ┌──────────────────────┐
                │  Circuit breaker     │   ← 2 consecutive hard
                │   src/llm/cost_…     │     failures → fast-fail 30s
                └──────────────────────┘
```

### 2.1 System prompts (token sink #1)

System prompts are the largest fixed cost on a cache miss. The full set is **~7,950 tokens** across all six agents.

We keep this manageable with three rules:

1. **Specialist prompts get a 25-token `TONE_HINT`.** Only the synthesizer pays the ~300-token `TONE_RULE + AUDIENCE_RULE` cost. The user-visible prose lives in the synthesizer alone, so paying the tone tax there is justified; paying it 5× for specialists is not.
2. **`@lru_cache` on every system-prompt builder.** The strings are built once per process, never on the hot path.
3. **Anchored rubrics over verbose CoT.** Most of the prompt token budget goes to the field-by-field rubric; chain-of-thought is one paragraph at most.

### 2.2 Synthesizer user prompt (token sink #2)

The synthesizer takes the 5 specialist outputs as JSON. We dump them with **`json.dumps(parts, separators=(',', ':'))`** instead of `indent=2` — saves ~30% of the bytes the model sees on a busy run, with zero information loss.

### 2.3 Image tokens (token sink #3)

Images are resized to a max edge of **1,024 px** before sending. At gpt-4o-mini's pricing, that's roughly **700 tokens per image**. Going lower (768 px) would save another 30% but blurs the small text the accessibility agent needs to grade.

### 2.4 Output tokens

`default_max_tokens=2048` is the hard cap per call. In practice every specialist's structured output lands well under that ceiling (typically 200-600 tokens); the synthesizer is the only call that sometimes brushes 1,500 tokens.

### 2.5 Pre-tools (the net token saver)

Each specialist runs zero or more **deterministic pre-tools** *before* the LLM. These are pure-Python measurements (PIL, OpenCV, NumPy) that produce ground-truth facts the LLM would otherwise have to invent:

| Agent | Pre-tool | What it produces |
| --- | --- | --- |
| visual | `extract_palette` | 3-6 hex codes via k-means in CIELab |
| accessibility | `estimate_text_size` | smallest / median / largest text-region px |
| brand | `palette_distance` | CIELab Δ-E between candidate and reference palettes |
| ux | `cta_density` | CTA-like word count from visual observations |

The pre-tools are real **LangChain `@tool`** decorated functions — registered via `src/agents/tools.py` and compatible with `model.bind_tools(...)` if any agent ever wants to expose them as model-callable tools. The same module also registers the **basic tools** (`read_file`, `list_files`, `web_search`) so a future routing node has read-only file IO + search out of the box.

Pre-tools cost **zero LLM tokens** and reduce the tokens the model spends speculating. They are auditable in the Settings → "Agent tools" card.

### 2.6 Caching

`src/llm/cost.py` wraps every call in a disk-backed cache. The key is `sha256(model + system + user + image-hash + temperature)`. A cache hit returns instantly with `cache_hit=True` recorded — no API call, no spend.

The cache is on by default. `CACHE_DISABLED=1` only makes sense in CI when you explicitly want every test run to repeat the upstream call. Cache invalidates automatically when you edit a prompt (because the system string is part of the key).

### 2.7 Circuit breaker

When OpenRouter returns 2 consecutive `_HARD_FAILURES` (auth, rate-limit, connection error) the circuit opens for 30 seconds and **all five agents fast-fail with `CircuitOpenError`**. This protects you against the worst case — a typo in the API key triggering 5 retries × 5 agents = 25 doomed network calls. With the breaker, you see the error after the second call.

State is visible in Settings → "Cost & resilience telemetry" → "Circuit breaker".

## 3. Quality gate + retry budget

The synthesizer runs a **pure-Python quality gate** on its first output. If a `fail`-severity issue is found (executive_summary too short, fewer than 3 recommendations, missing breakdown axes), it re-prompts ONCE with the specific failure list appended. Hard rules:

- **Max 1 retry per agent.** No retry storms.
- Retry is **skipped when `CACHE_DISABLED=1`** so CI runs are repeatable.
- Worst case cost = `2× synthesizer call ≈ 0.0015 USD per run`. Almost free.

## 4. Cost math for a typical real-API run

Single screenshot, no cache hits, default models (`gpt-4o-mini`):

| Agent | Prompt tok | Output tok | Image tok | USD |
| --- | --- | --- | --- | --- |
| visual | 1,160 | 350 | 700 | $0.000489 |
| ux | 1,220 | 450 | 700 | $0.000558 |
| accessibility | 1,050 | 350 | 700 | $0.000473 |
| brand | 1,150 | 300 | 700 | $0.000458 |
| market | 1,000 | 400 | 0 | $0.000390 |
| synthesizer | 4,400 | 850 | 0 | $0.001170 |
| **Total** | | | | **~$0.0035** |

**~⅓ of a cent per analysis at default settings.** With a 50% cache hit rate (a typical demo with one or two images you analyze repeatedly), it's closer to **$0.002**.

For comparison, switching the defaults to Claude 3.5 Sonnet ($3 / $15 per Mtok) would push a single run past **$0.06** — a 17× swing. The defaults exist on purpose.

## 5. Observability

The Settings tab shows everything live:

- Total LLM calls, cache hits, cache misses
- Prompt + completion + total tokens
- Estimated USD (per model and total)
- Circuit breaker state (closed / open with cooldown)
- The full registered tool list per agent

Click "Refresh telemetry" after any run.

## 6. Anti-hallucination policy as a cost control

This is the under-appreciated cost lever. Every system prompt carries an `ANTI_HALLUCINATION_RULE` and an `ABSTENTION_RULE` (in `src/utils/prompts/_shared.py`). They explicitly tell the model to abstain — emit `null`, `[]`, or "not measurable" — when evidence is missing rather than fabricating something plausible.

Why this saves money:

- **Shorter outputs.** A model that abstains writes 3 grounded recommendations instead of 5 padded ones. Median completion-token spend drops measurably.
- **Fewer retries.** The synthesizer's quality-gate retry triggers when fields are missing or thin. Strong abstention rules mean the gate fires less often.
- **Better cache hit rate.** Grounded outputs are more deterministic at temperature 0.2 than fabricated ones, so the disk cache hits more reliably on repeat demos.

The rules are pinned by `tests/test_prompts.py` so a future refactor cannot silently delete them.

## 7. Things you can do to spend even less

1. **Use the offline fakes** (`USE_REAL=false` in `.env`). Zero tokens, perfect for demos and tests.
2. **Use the same image twice.** The cache makes the second run free.
3. **Skip the market agent for non-public flows.** It is the only specialist that does web search and can be the chattiest. There is currently no UI toggle but the graph wiring in `src/agents/graph.py` is one boolean away.
4. **Bring your own image index.** `make ingest` populates LanceDB; the brand agent's `palette_distance` then uses your real reference palette instead of guessing.

---

If you find a token leak this doc does not describe, that is a bug. Open an issue with a `cost_tracker.snapshot()` dump from before and after.
