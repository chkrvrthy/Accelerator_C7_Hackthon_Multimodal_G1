# Person D — UX + Accessibility Agents

> **Mission.** You critique. Findings without evidence are not allowed. If a
> Finding cannot quote what it saw, it gets cut.

## Why your slice exists (concepts you are demonstrating)

| Sprint | Concept | What you ship |
|---|---|---|
| 1 | XML-tagged prompt structure (`<context>`, `<task>`) | `src/agents/ux_critique.py` |
| 1 | WCAG criterion-aware prompts | `src/agents/accessibility.py` |
| 6 | Two more parallel branches of the fan-out | both files |

You also bring the only optional deterministic signal in the system: a small
opencv contrast pass that overrides `AccessibilityReport.contrast_pass` with
a measured value. The LLM never overrides a measured number.

## Files you own

| File | One-line purpose |
|---|---|
| `src/agents/ux_critique.py` | `run(state, deps)` → `{"ux": UXCritique}`; runs `cta_density` pre-tool. |
| `src/agents/accessibility.py` | `run(state, deps)` → `{"accessibility": AccessibilityReport}`; runs `estimate_text_size` pre-tool first. |
| `src/utils/prompts/ux.py` | UX system + user prompts (LRU-cached, anti-hallucination + closed Nielsen list). |
| `src/utils/prompts/accessibility.py` | Accessibility system + user prompts (closed WCAG SC list to prevent SC fabrication). |
| `src/schemas/outputs.py` (your two output models) | `UXCritique`, `AccessibilityReport`. |
| `tests/person_d/*` | Your test slice. |

## Contracts you consume

```python
class VisionLLM(Protocol):
    def analyze(self, *, system, user, images, schema, model=None) -> BaseModel: ...
```

That is it. No retriever, no web search, no special seams. Your slice is the
purest example of "give the model an image, ask for typed JSON".

## Setup — first 5 minutes (do exactly this)

### 1. Clone and create a venv

**Linux / macOS:**

```bash
git clone <repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-d-agents.txt
```

**Windows (PowerShell):**

```powershell
git clone <repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-d-agents.txt
```

`person-d-agents.txt` pulls `opencv-python` for the optional deterministic contrast measurement. You can skip it with `pip install -e ".[dev]" -r requirements/base.txt` and the agent's contrast logic still works (LLM-judged instead of measured).

### 2. Keys you need

| Key | Mandatory for Person D? | Where to get it | Free tier? |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Yes** for `USE_REAL=1` runs (your prompt iteration loop on real screenshots needs a real LLM) | https://openrouter.ai/keys | Pay-as-you-go (~$0.001 per agent run; iterate freely) |

You can do **80% of your work with the fakes** — schema validity, severity rubric tests, and the deterministic contrast measurement are all offline.

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
python -c "from src.config import settings; print('key set:', bool(settings.openrouter_api_key)); import cv2; print('opencv:', cv2.__version__)"
# Expect: key set: True   opencv: 4.x.x  (or ImportError if you skipped opencv — fine)
```

### 5. First successful run

```bash
make test-d                                        # offline (fakes)
make run-d-ux                                      # against fakes
make run-d-a11y                                    # against fakes
USE_REAL=1 make run-d-ux                           # against real OpenRouter
USE_REAL=1 make run-d-a11y                         # against real OpenRouter — opencv runs deterministic contrast
```

The accessibility agent logs `agent.accessibility: ok (AccessibilityReport)` on success. If contrast is measured deterministically, you'll see the override line in the log; if not, the LLM's guess stays.

## Run-in-isolation

```
make run-d-ux                    # uses fakes by default
make run-d-a11y
USE_REAL=1 OPENROUTER_API_KEY=... make run-d-ux
```

## Smoke tests

```
make test-d
```

## Implementation hot-spots

1. **`accessibility.run` — opencv contrast pass.** Where the TODO says
   "if opencv is installed" — load the image, find foreground/background pairs
   from histogram peaks, compute the WCAG relative-luminance ratio, set
   `result.contrast_pass = ratio >= 4.5`. This deterministic signal beats
   the LLM's guess every time.
2. **`utils.prompts.ux_critique_system` rubric.** Add the severity rubric
   ("high = blocks task completion, medium = friction, low = polish") so the
   LLM stops marking everything as `critical`.
3. **`utils.prompts.accessibility_system` SC numbers.** The current prompt
   says "reference WCAG SC". Make it stricter: "EVERY finding must cite a
   numeric criterion (e.g. 1.4.3, 2.5.5). No criterion → no finding."

## Done when

- [ ] `make test-d` is green from a fresh `.venv`.
- [ ] Both agents produce schema-valid `UXCritique` / `AccessibilityReport`
      for the bundled sample.
- [ ] Each finding has non-empty `evidence` AND `recommendation` strings.
- [ ] When opencv is installed, `contrast_pass` is set deterministically.

## Common pitfalls

- **Severity inflation.** See above. Anchor to a rubric in the prompt.
- **Mixing WCAG 2.1 vs 2.2 SC numbers.** WCAG 2.2 added a few criteria
  (e.g. 2.5.7, 2.5.8). If your prompt allows both, the model gets confused.
- **Generic recommendations.** "Improve contrast" is not a recommendation;
  "raise body-text color from `#7C7C7C` to `#444` to meet 4.5:1" is.
