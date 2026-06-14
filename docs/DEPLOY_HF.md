# Deploy to Hugging Face Spaces

> A 5-minute guide to put this project on a free CPU Space. Zero cost
> in offline-fakes mode; ~$0.03/run with `OPENROUTER_API_KEY` set.

This is the **cheapest way to demo the project publicly**. HF Spaces gives you:

- A persistent URL: `https://huggingface.co/spaces/<user>/<space>`.
- A free CPU runtime — every specialist agent is LLM-bound (OpenRouter
  does the heavy lifting), so CPU is fine. No GPU needed.
- Build logs you can read and a "Restart Space" button you can click.
- Free SSL, free domain, sleeps after 48 h of no traffic and wakes on
  the next request (~30 s cold start).

The default offline-fakes mode runs with **zero API keys** and zero
cost. Add an `OPENROUTER_API_KEY` secret only when you want the real
five-agent panel.

---

## What's already wired up

We pre-built the Spaces scaffolding. None of the file names below are
optional — HF reads them by exact name.

| File | Why it's there |
| --- | --- |
| `app.py` (root) | HF auto-runs this. It's a 5-line shim that imports `ui.app:main`. |
| `requirements.txt` (root) | The single dependency manifest HF reads. Contains the runtime superset only — no dev/test deps. |
| `README.md` (root) | Frontmatter (`sdk: gradio`, `app_file: app.py`, `sdk_version`) drives the Space build. The rendered body becomes the Space's About page. |
| `ui/app.py` | The actual Gradio app. **HF-aware** — binds to `0.0.0.0` automatically when `SPACE_ID` is set, falls back to `127.0.0.1` for local dev. No code change needed. |

If any of those file names drift, HF will silently fail to start the
app — you'll see "Build error" with no logs. Always look at the
**Logs** tab first.

---

## Step 1 — Confirm the README frontmatter

Open `README.md` and confirm the **first 11 lines** are this YAML
frontmatter (already committed):

```yaml
---
title: Multimodal AI Design Analysis Suite
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "6.18.0"
app_file: app.py
pinned: false
license: mit
short_description: Multi-agent design review with image RAG and OpenRouter.
---
```

Only those keys matter. Anything else in the YAML is ignored. **Pin
`sdk_version` to the same major as `gradio>=...,<...` in
`requirements.txt`** — version skew here is the #1 build failure on
Spaces. Both are currently pinned to `6.18.0` / `>=6.18.0,<7.0`.

---

## Step 2 — Create the Space on huggingface.co

1. Visit <https://huggingface.co/new-space>.
2. **Owner**: your username or org.
3. **Space name**: anything URL-safe — e.g. `design-analysis-suite`.
4. **License**: MIT (matches the repo).
5. **SDK**: choose **Gradio**.
6. **Hardware**: CPU basic (free) — enough for an LLM-bound app.
7. **Visibility**: Public is fine for a hackathon submission. Private
   needs a paid HF subscription.
8. Click **Create Space**. You'll land on an empty Space's "Files"
   page — that's your push target.

---

## Step 3 — Wire the HF remote and push (two ways)

Hugging Face Spaces are git repos; `git push` is the deploy.

### Option A: One-shot, recommended (Make targets)

We ship two convenience targets. They never write your token to disk
and redact it from the printed command.

```bash
# 1. Generate a write token at https://huggingface.co/settings/tokens
#    and export it in your shell (do NOT commit it).
export HF_TOKEN=hf_...

# 2. Wire the 'hf' remote (one time per repo):
make hf-remote HF_USER=<your-user> HF_SPACE=<space-name>

# 3. Push (every time you want to deploy):
make hf-push
```

`make hf-push` uses the inline-URL technique
(`https://USER:$HF_TOKEN@huggingface.co/...`) so the token is consumed
once and never persisted in `.git/config`.

### Option B: Manual git

If you'd rather drive `git` directly:

```bash
git remote add hf https://huggingface.co/spaces/<your-user>/<space-name>
git push hf main
```

When prompted for credentials, use:

- **Username**: any non-empty string — HF ignores it for token auth.
- **Password**: your HF write token (`hf_...`).

The Space will start building — watch the **Logs** tab. **First
builds are slow (~5–8 min)** because PyTorch + open_clip download
wheels. Subsequent builds use the cache (~90 s).

---

## Step 4 — Add secrets (only for real APIs)

Default behavior is offline fakes — works without any keys. To switch
to the real five-agent panel:

1. Open your Space → **Settings** → **Repository secrets**.
2. Add **`OPENROUTER_API_KEY`** with your OpenRouter key (`sk-or-...`).
3. *(Optional)* Add **`TAVILY_API_KEY`** for live web search in the
   market agent. Without it, the market agent falls back to
   DuckDuckGo (still works, just rate-limited).
4. *(Optional)* Add **`LANGSMITH_API_KEY`** to ship traces. Without it,
   the project's `tracing.py` module installs a no-op tracer.
5. Now go to **Settings → Variables** (above secrets) and add the
   non-secret toggle:
   - `USE_REAL=true` — flips the default mode to real APIs.
6. Click **Restart Space**.

The Space's **Settings tab** inside the running app will then show
`OPENROUTER_API_KEY loaded: True` and the cost telemetry card will
populate after every Run.

---

## Step 5 — Smoke-test the deploy

After the build succeeds:

1. Open the Space URL.
2. **Quickstart**: in the Analyze tab, click the
   "Try the bundled sample (one-click prefill)" row. Form auto-fills.
3. Click **Run analysis**.
4. Watch the streaming status block:
   - `Analysis running` — the orchestrator is fanning out.
   - `Report ready — Score: X/100 across 1 frame.` — done.
5. Open the **Report** tab. Verify the score block, breakdown bars,
   and recommendation cards render. If you see the orange
   "Review needed" banner, click **"What does this mean?"** for
   the explainer (an empty narrative on the Visual agent is the most
   common cause; on free Spaces with `gpt-4o-mini`, the visual
   self-heal retry usually recovers it).
6. Open the **References** tab. The top "References used in this run"
   card will be empty (no `data/reference/` images on the Space yet)
   — that's expected. Type `fintech payments landing page hero
   gradient` in the search box, hit Enter; you should see web hits
   (Tavily or DuckDuckGo) and a hand-curated editorial fallback row.
7. Open the **Settings** tab. Confirm:
   - `OPENROUTER_API_KEY loaded: True/False` matches your secrets.
   - `Indexed reference rows: 0` (the corpus is empty on a fresh Space).
   - Cost telemetry card shows your per-Run tokens + USD.

If the demo is offline (no `OPENROUTER_API_KEY` secret) the app still
works — every agent uses the deterministic fakes, the score lands at
~74.5, and you've still proven the full UI works end-to-end.

---

## Step 6 — Seed the brand-RAG corpus (optional)

A fresh Space has zero indexed reference rows. The brand agent and
References tab will gracefully no-op (the editorial fallback handles
empty corpus), but the demo looks better with a few thumbnails.

**Two ways to seed:**

### A. Commit reference images (simplest, ~10 MB max)

Drop a handful of public-domain UI screenshots into `data/reference/`
locally, commit them, push to HF. They'll be re-ingested on the next
container restart **only if** you also commit the resulting LanceDB
files in `data/index/` — but those are binary blobs and Git LFS would
help. For the hackathon, the simpler path is a **boot-time ingest**:

### B. Boot-time ingest hook (recommended)

Add this to a top-of-`app.py` startup block (or rely on the existing
`ensure_dirs()` if you wire it into your own bootstrap). HF builds the
container fresh each restart, so this only runs once per container
lifetime:

```python
import subprocess, sys
from pathlib import Path
from src.config import get_settings

cfg = get_settings()
if cfg.local_reference_file_count() and cfg.vector_row_count() == 0:
    subprocess.run(
        [sys.executable, "-m", "scripts.ingest_references",
         "--source", str(cfg.reference_dir)],
        check=False,
    )
```

Or just commit the LanceDB index folder (`data/index/`) along with
the reference images. Both work; the boot-time ingest is more
hermetic and easier to update.

---

## Cost expectations

| Mode | Per-run cost | Notes |
| --- | --- | --- |
| Offline fakes (default, no `OPENROUTER_API_KEY`) | **$0** | Returns in <1 s. Demo-grade payload from `src/fakes/`. |
| Real APIs, single frame (`gpt-4o-mini`) | **~$0.03** | ~25 s end-to-end. ~22 k tokens across 5 agents. |
| Real APIs, 3 frames | **~$0.05** | ~40 s. Comparison mode shares vision tokens. |
| Real APIs, 5 frames | **~$0.08** | ~55 s. The 5-frame ceiling is the upload preflight cap. |
| Stronger vision model (`anthropic/claude-3.5-sonnet`) | **~$0.20/run** | 7× cost vs `gpt-4o-mini`, but the visual self-heal retry rate drops near zero. Set in `.env` via `DEFAULT_MODEL=anthropic/claude-3.5-sonnet`. |

A community-tier (free) Space sleeps after 48 h of no traffic. The
first request after sleeping takes ~30 s to wake the container. This
is normal and costs nothing.

---

## Persistence caveat (important for demos)

Free Spaces have **ephemeral disk**. That means:

- `data/reports/design_report_<ts>_<run_id>.json` files **survive only
  until the Space restarts**. The runtime cache, app log, and
  ingested LanceDB rows all live in the same boat.
- The "App log file" path shown in the Settings tab still works
  during a single session — you can `tail` it via the Space's
  built-in **Files** browser if you have the right permissions —
  but it's gone after a rebuild.
- This is fine for the demo: the score on screen + JSON-export from
  the Report tab is the canonical artifact. Long-term retention is
  the user's responsibility.

If you need persistence (e.g. to keep the LanceDB corpus across
restarts):

- Upgrade to **Persistent storage** (Settings → Hardware → Add
  persistent storage, $5/mo for 20 GB).
- Or move to a paid tier (`a10g-small`, $0.40/h) for both GPU AND
  persistent disk.
- Or: keep your reference corpus in a public dataset on HF and
  pull it at boot via `huggingface_hub`.

---

## Common build failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: ui` | App can't find the package | Confirm `app.py` is at the **root** and contains `from ui.app import main`. |
| Build times out (~10 min) | Torch + open_clip wheels are slow | Wait. Only the first build hits this; rebuilds are cached. |
| `gradio` version mismatch | YAML `sdk_version` ≠ `requirements.txt` pin | Pin both to the same minor version (`6.18.0`). |
| Blank page after deploy | Server bound to 127.0.0.1 instead of 0.0.0.0 | Already fixed — `ui/app.py` auto-detects `SPACE_ID`. If a fork removed the detection, restore it. |
| `OPENROUTER_API_KEY not set` errors at runtime | Secret missing | Set under **Settings → Repository secrets**, then **Restart Space**. |
| Quota / rate-limit on real-API mode | Free tier on OpenRouter exhausted | Top up, or switch to fakes by removing `USE_REAL=true` variable and restarting. |
| `agent.visual: shallow response (palette-only)` warning | `gpt-4o-mini` rejected `json_schema` | Expected. The visual self-heal retries once; if it stays shallow the report still renders with `<i>not captured</i>` placeholders. Switch `DEFAULT_MODEL` to `anthropic/claude-3.5-sonnet` if it persists. |
| App log empty when you `tail` it on the Space | `LOG_TO_FILE` env var not set | Default is on. If a fork set `LOG_TO_FILE=0` for headless workers, remove it. |

---

## Updating the deployed Space

```bash
git commit -am "tweak prompt"

git push origin main         # GitHub mirror
make hf-push                 # HF Space (assumes HF_TOKEN exported)
```

HF rebuilds on every push to its `main` branch. Use the **Logs** tab
on the Space to watch the build. If the build fails, the previous
Space version stays live.

For more drastic changes (new dependencies, switching the SDK
version), trigger a **factory rebuild** from Settings → "Factory
reboot" so the build cache is invalidated.

---

## What the Space looks like end-to-end

A properly deployed Space serves four tabs in order:

1. **Analyze** — single + multi-frame upload (1–5 PNG/JPG/WEBP),
   frame-labels textbox, free-form context, mode banner reading from
   `.env` / Spaces secrets, "Try the bundled sample" prefill row.
2. **Report** — 44 px score pill, optional "Review needed" banner
   with disclosure, score-rationale paragraph, five breakdown bars,
   per-frame heatmap (multi-frame only), top strengths, prioritized
   recommendation cards (priority/effort/impact/metric_lift/proof),
   five collapsible specialist accordions.
3. **References** — two stacked sections. Top auto-fills with the
   brand thumbnails + market URLs the agents actually consulted.
   Bottom is an ad-hoc search box hitting LanceDB + Tavily/DDG +
   editorial fallback in parallel.
4. **Settings** — three cards. Current configuration (12 rows tagged
   `.env` / `code` / `auto`), live cost telemetry (auto-refreshes
   after every Run), tool registry (every LangChain `@tool` we ship).

Plus a launch banner in the Logs tab printing
`* Logs are tee'd to: /home/user/app/data/logs/app.log`. Every run is
bracketed by `RUN START session=<id>` / `RUN END session=<id>` lines
so you can grep the rolling log by session id.

---

## Why HF over Vercel / Render / Fly?

- HF is the only platform on this list that already understands
  Gradio. No nginx config, no port surgery, no cold-start surgery.
- Free CPU tier is enough for an LLM-bound app — all the heavy work
  is upstream of the container.
- You don't pay for cold-start; community Spaces just take a few
  seconds to wake on first request.
- The `huggingface.co/spaces/...` URL is presentation-friendly for
  hackathon judges (recognizable, no toy-domain feel).
- Bonus: the Space's About page renders your README, so judges can
  read the architecture diagram and FAQ without leaving the
  hosting site.

If you ever outgrow the free tier, **HF "ZeroGPU"** (`a10g-small`)
is the next step — same `app.py`, you only change the hardware in
Settings. That's $0.40/h on demand.
