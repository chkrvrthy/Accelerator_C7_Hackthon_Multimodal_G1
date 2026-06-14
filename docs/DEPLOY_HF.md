# Deploy to Hugging Face Spaces

> A 5-minute guide to put this project on a free CPU Space (or pay $0.40/hr for GPU when needed).

This is the **cheapest way to demo the project publicly**. HF Spaces gives you:

- A persistent URL (`https://huggingface.co/spaces/<user>/<space>`).
- A free CPU runtime that handles all 5 specialist agents (they're LLM-bound, not compute-bound — CPU is fine).
- Build logs you can read and re-build on demand.

The default offline-fakes mode runs with **zero API keys** and zero cost. Add an `OPENROUTER_API_KEY` secret only when you want the real model council.

---

## What's already in the repo

We pre-wrote everything HF needs:

| File | Purpose |
| --- | --- |
| `app.py` (root) | HF Spaces auto-runs this; it imports `ui.app:main` |
| `requirements.txt` (root) | The single dependency manifest HF reads |
| `README.md` (root) | The Space description; HF expects YAML frontmatter (see below) |

If you renamed any of these, HF will silently fail to start the app.

---

## Step 1: Add the HF YAML frontmatter to README.md

Open `README.md` and make sure the **very first** line is `---`. Replace the existing top of the file with this header (everything from the second `---` down stays as is):

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

The keys above are the ones HF actually reads. Anything else in the YAML is ignored.

## Step 2: Create the Space

1. Visit https://huggingface.co/new-space.
2. **Owner**: your username or org.
3. **Space name**: anything URL-safe (e.g., `design-analysis-suite`).
4. **License**: MIT (or whatever matches your repo).
5. **SDK**: Gradio.
6. **Hardware**: CPU basic (free) is enough.
7. Make it public (or private if you have a paid HF account).
8. Click **Create Space**.

You'll land on an empty Space's "Files" page.

## Step 3: Push your repo to the Space

Hugging Face Spaces are git repos. Add the Space as a remote and push:

```bash
git remote add hf https://huggingface.co/spaces/<your-user>/<space-name>
git push hf main
```

If you get a credential prompt, log in with your HF username and an HF write token (from https://huggingface.co/settings/tokens).

The Space will start building — watch the **Logs** tab. First builds are slow (~5-8 minutes) because PyTorch + open_clip download wheels. Subsequent builds use the cache.

## Step 4: Add secrets (only if you want real APIs)

Default behavior is offline fakes — works without any keys. To switch to real APIs:

1. Open your Space → **Settings** → **Repository secrets**.
2. Add `OPENROUTER_API_KEY` with your OpenRouter key.
3. *(Optional)* Add `TAVILY_API_KEY` for live web search in the market agent.
4. Add a regular variable `USE_REAL=true` (in **Variables** above secrets).
5. Click **Restart Space**.

The Settings tab inside the running app will then show "Real API key loaded: True" and the cost telemetry will populate.

## Step 5: Test the deploy

After the build succeeds:

1. Open the Space URL.
2. Drag the bundled sample (`src/fakes/fixtures/sample.png`) into the upload box.
3. Click **Run analysis**.
4. Watch the streaming status. Open the Report tab; verify the executive summary, breakdown bars, and recommendation cards render.
5. Open the Settings tab → click **Refresh telemetry** → verify the cost ledger lit up (with real APIs) or stayed at zero (with fakes).

If the demo is offline (no `OPENROUTER_API_KEY` secret) the app still works — every agent uses the deterministic fakes.

---

## Cost expectations on Spaces

- **Free CPU tier**: $0/month for the runtime. You only pay for any LLM tokens you burn through OpenRouter (default model gpt-4o-mini → ~⅓ of a cent per analysis; see `docs/COST_DISCIPLINE.md`).
- **GPU tier**: not needed unless you switch the visual agent to a local CLIP-large or a vision model that runs on the Space itself. Default deployment is API-bound, no GPU help possible.

A community-tier Space sleeps after 48 hours of no traffic. The first request after sleeping takes ~30s to wake the container; this is normal and costs nothing.

## Common build failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: ui` | App can't find the package | Confirm `app.py` is at the **root** and contains `from ui.app import main` |
| Build times out | Torch + open_clip wheels are slow | Wait — only the first build hits this; rebuilds are cached |
| `gradio` version mismatch | YAML `sdk_version` ≠ requirements.txt | Pin both to the same minor version |
| `OPENROUTER_API_KEY not set` errors at runtime | Secret missing | Set it under Settings → Repository secrets |
| Quota / rate-limit on real-API mode | Free tier on OpenRouter exhausted | Top up or switch back to `USE_REAL=false` |

## Updating the deployed Space

```bash
# Make a change locally, commit it
git commit -am "tweak prompt"

# Push to your origin (the GitHub mirror) and to HF
git push origin main
git push hf main
```

HF will rebuild on every push. Use the **Logs** tab to watch.

---

## Why HF over Vercel / Render / Fly?

- HF is the only platform on this list that already understands Gradio.
- Free CPU tier is enough for an LLM-bound app.
- You don't pay for cold-start; community Spaces just take a few seconds to wake.
- The Space URL is presentation-friendly for hackathon judges.

If you ever outgrow the free tier, HF "ZeroGPU" (`a10g-small`) is the next step — same `app.py`, you only change the hardware in Settings.
