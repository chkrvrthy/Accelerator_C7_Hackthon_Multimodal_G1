# Deploy to Hugging Face Spaces — beginner's guide

> Goal: get this project running on a free public website at
> `https://huggingface.co/spaces/<your-name>/<your-space>` so anyone
> with the link can use it. **No prior deployment experience required.**
> If you can copy and paste, you can finish this in 15 minutes.

---

## Before you start (one-time setup, ~5 minutes)

You need three things on your computer. Skip any you already have.

### 1. Make a Hugging Face account

1. Open <https://huggingface.co/join> in your browser.
2. Sign up with email or GitHub (either works).
3. Verify your email when they send the link.
4. Pick a username — that's the `<your-name>` in your future Space URL.

### 2. Get a Hugging Face "write token"

A token is like a password that only works for one specific thing.
We need one that's allowed to push code.

1. Make sure you're logged in to Hugging Face.
2. Go to <https://huggingface.co/settings/tokens>.
3. Click the **New token** button (top right).
4. Fill in the form:
   - **Name**: type `design-suite-deploy` (anything works, this is just a label)
   - **Type**: click **write** (this is critical — `read` won't work)
5. Click **Generate token**.
6. A long string starting with `hf_` will appear — that's your token.
   **Copy it now.** Hugging Face won't show it to you again. Paste it
   somewhere safe like a password manager or a temporary text file.

### 3. Confirm you have git

Open a terminal:

- **macOS**: press `Cmd+Space`, type `Terminal`, press Enter.
- **Linux**: press `Ctrl+Alt+T`.
- **Windows**: search "Git Bash" in the Start menu (install it from
  <https://git-scm.com/downloads> if it's not there).

In the terminal, type and press Enter:

```bash
git --version
```

You should see something like `git version 2.42.0`. If you see "command
not found", install git from <https://git-scm.com/downloads> and try
again.

That's all the setup. The rest is on the actual project.

---

## Step 1 — Make sure everything in the repo is good

You should already be inside the project folder. If not, navigate to it:

```bash
cd /path/to/ai_c7_hackathon
```

Run this **one-time check** to confirm the three files Hugging Face
needs are present:

```bash
ls app.py requirements.txt README.md
```

You should see all three filenames printed, no "No such file" errors.
If anything's missing, stop here and ask for help — those files must
exist or the deploy will fail silently.

> **What does each file do?**
> - `app.py` — the file Hugging Face runs to start the website. It's
>   only 5 lines; it imports the real app from `ui/app.py`.
> - `requirements.txt` — the list of Python libraries the app needs.
>   Hugging Face installs these automatically.
> - `README.md` — the project description. The first 11 lines are
>   special "frontmatter" that tells Hugging Face this is a Gradio app.

---

## Step 2 — Create the Space on the Hugging Face website

This is all in the browser. **You don't run any commands here.**

1. Go to <https://huggingface.co/new-space> in your browser.
2. Fill in the form:

   | Field | What to type | Why |
   | --- | --- | --- |
   | **Owner** | your username | This is the `<your-name>` part of the URL. |
   | **Space name** | `design-analysis-suite` | Short and URL-safe. Lowercase, no spaces, hyphens are fine. |
   | **License** | choose **MIT** | Matches the repo's license. |
   | **Select the Space SDK** | click **Gradio** | Our app is a Gradio app. |
   | **Hardware** | leave on **CPU basic — Free** | All the heavy work happens at OpenAI/OpenRouter, so a free CPU is plenty. |
   | **Public/Private** | choose **Public** | (Private requires a paid HF account.) |

3. Click the big **Create Space** button at the bottom.
4. You'll land on a page that looks empty with a "Files" tab. **Leave
   this browser tab open** — we'll come back to it.

> **Tip**: write down the URL you just made. It looks like
> `https://huggingface.co/spaces/<your-name>/design-analysis-suite`.
> That's where your live app will be in about 10 minutes.

---

## Step 3 — Push your code to the Space

The Space is just an empty git repo right now. We need to upload our
code into it. The project ships with two Make commands that do this.

In your terminal (still inside the project folder), do these in order:

### 3a. Save the token as an environment variable

Replace `hf_xxx_PUT_YOUR_REAL_TOKEN_HERE` with the actual token you
copied in "Before you start" step 2:

```bash
export HF_TOKEN=hf_xxx_PUT_YOUR_REAL_TOKEN_HERE
```

> **What does `export` do?** It puts the token into your terminal's
> memory so the next commands can read it without you typing it again.
> When you close the terminal, the token is forgotten.

### 3b. Tell git where to push (one-time)

Replace `<your-name>` with your Hugging Face username and
`<space-name>` with what you typed in Step 2 (probably `design-analysis-suite`):

```bash
make hf-remote HF_USER=<your-name> HF_SPACE=<space-name>
```

You should see something like:

```text
Adding 'hf' remote -> https://huggingface.co/spaces/<your-name>/<space-name>
hf  https://huggingface.co/spaces/<your-name>/<space-name> (fetch)
hf  https://huggingface.co/spaces/<your-name>/<space-name> (push)
```

That's the success message.

### 3c. Push the code

```bash
make hf-push
```

You should see lines like:

```text
Pushing HEAD -> hf/main ...
remote: ----
remote: Hugging Face Spaces upload complete.
To https://huggingface.co/spaces/<your-name>/<space-name>
 * [new branch]      HEAD -> main
```

That's it — your code is now on Hugging Face. The Space starts
building immediately. **Switch to your browser tab** with the Space
open. You'll see a yellow "Building" banner.

---

## Step 4 — Wait for the build (5–8 minutes the first time)

In your browser:

1. Click the **Logs** tab at the top of your Space.
2. Watch the lines stream by. You're looking for:
   - **"Installing dependencies..."** — installing Python libraries (~3-5 min).
   - **"Building the application..."** — packaging up the app (~30 sec).
   - **"Running on local URL"** — the moment your app is alive.
3. When you see green text saying the app is running, click the **App**
   tab. Your live app should appear.

> **Why is the first build slow?** It downloads big Python libraries
> (PyTorch is ~700 MB by itself). Hugging Face caches them, so every
> rebuild after this one takes 60–90 seconds, not 5+ minutes.

If the build fails (red text instead of green), see the
"Common problems" section at the bottom of this guide.

---

## Step 5 — (Optional) Add API keys for "real" mode

By default the app works with NO API keys — it uses fake offline data
that returns instantly. Good for showing the UI. But the real demo
shines when it actually calls AI models.

To switch to real mode:

1. In your browser, on your Space's page, click the **Settings** tab
   (top right, next to "Files" and "Community").
2. Scroll down to **Repository secrets**. Click **New secret**.
3. Add the OpenRouter key:
   - **Name**: `OPENROUTER_API_KEY`
   - **Value**: paste your OpenRouter key (starts with `sk-or-...`).
     Get one at <https://openrouter.ai/keys> if you don't have one.
   - Click **Save**.
4. *(Optional)* Add Tavily for live web search in the market agent:
   - Click **New secret** again.
   - **Name**: `TAVILY_API_KEY`
   - **Value**: your Tavily key from <https://app.tavily.com/home>.
   - Click **Save**.
5. Now scroll up to **Variables** (above the Secrets section). Add a
   regular variable (not a secret):
   - Click **New variable**.
   - **Name**: `USE_REAL`
   - **Value**: `true`
   - Click **Save**.
6. Scroll to the very top of the Settings page and click
   **Restart this Space**. Wait ~30 seconds for it to come back up.

When the app finishes restarting, open the **Settings tab inside the
running app** (not the HF settings — the tab at the top of the actual
Gradio app). You should see:

- `OPENROUTER_API_KEY loaded: True`
- `USE_REAL: true`

That confirms real mode is on.

---

## Step 6 — Test that everything works

In your browser, on the live Space:

1. **Analyze tab**: click the row that says
   "Try the bundled sample (one-click prefill)". The form auto-fills.
2. Click the green **Run analysis** button.
3. Watch the status messages:
   - "Analysis running" → "Reviewing sample with offline fakes." (or
     "real APIs (.env)" if you did Step 5)
   - "Report ready — Score: X/100..."
4. Click the **Report tab** at the top. You should see:
   - A big green score pill (around 70-80 for fakes, 70-85 for real).
   - "Top strengths" bullet list.
   - "Prioritized recommendations" cards.
5. Click the **Settings tab inside the app**. Confirm the configuration
   card shows the right values.

If any of those steps don't look right, see "Common problems" below.

---

## How to update the app later

After you change code locally:

```bash
git add .
git commit -m "describe what you changed"
git push origin main      # to GitHub
make hf-push              # to Hugging Face (rebuilds the Space)
```

The HF rebuild kicks off automatically. Watch the Logs tab. If the
new build fails, the previous version stays live — your app never
goes down because of a broken push.

> Make sure `HF_TOKEN` is still in your terminal's memory. If you've
> opened a fresh terminal, run `export HF_TOKEN=hf_...` again before
> `make hf-push`.

---

## Can the app run BOTH on my laptop AND on Hugging Face?

**Yes — and that's already how it's wired.** No environment-specific
code branches. The same `app.py` works in both places because:

- `ui/app.py` checks for the `SPACE_ID` environment variable that
  Hugging Face sets automatically. If it's set, the server binds to
  `0.0.0.0` (so the Space's front-door proxy can reach it).
- If `SPACE_ID` is not set, the server binds to `127.0.0.1` (localhost
  only — keeps your app off the LAN by default for privacy).
- You can override either way with the `GRADIO_SERVER_NAME` env var
  (useful for Docker containers, CI, etc.).

So the same workflow works:

| Where | Command | Where it runs |
| --- | --- | --- |
| Your laptop | `make ui` (or `python ui/app.py`) | <http://127.0.0.1:7860> |
| Hugging Face Space | `make hf-push` | `https://huggingface.co/spaces/<you>/<space>` |

Both run the **identical code**. Both produce the same UI. Both can
use real APIs (your laptop reads `.env`; the Space reads its
"Repository secrets"). The launch banner prints the path to the log
file in either environment.

---

## What does it cost?

| Mode | Per analysis | Notes |
| --- | --- | --- |
| Offline fakes (no `OPENROUTER_API_KEY`) | **$0** | Returns in <1 s. Demo-grade fixed responses from `src/fakes/`. |
| Real APIs, single screenshot | **~$0.0085** | Default model is `openai/gpt-5-mini` — $0.25 input / $2.00 output per 1M tokens. ~25 s end-to-end. |
| Real APIs, 3 screenshots | **~$0.020** | Comparison mode shares vision tokens efficiently. |
| Real APIs, 5 screenshots | **~$0.034** | The 5-frame ceiling is enforced by the upload preflight. |
| Cheaper option (`openai/gpt-5-nano`) | **~$0.002** per single-frame | $0.05 input / $0.40 output per 1M tokens. Self-heal retry fires more often, but most runs still succeed in one pass. |
| Stronger option (`anthropic/claude-3.5-sonnet`) | **~$0.10** per single-frame | $3.00 input / $15.00 output per 1M tokens. Gold-standard vision quality, ~12× the cost. |

Free Spaces sleep after 48 hours of no traffic and wake on the next
request (~30 s cold start). That's normal and free.

> **Want to switch models?** Two options:
> 1. In Step 5 above, also add a Variable (not a secret):
>    - Name: `DEFAULT_VISION_MODEL`, Value: `openai/gpt-5-nano`
>    - Name: `DEFAULT_TEXT_MODEL`, Value: `openai/gpt-5-nano`
>    - Restart the Space.
> 2. Or locally, edit `.env` and set the same two lines, then run
>    `make ui` — the Settings tab will show the new model name.

---

## What does the deployed app look like?

A working Space serves four tabs in this order:

1. **Analyze** — upload 1 to 5 screenshots, type optional context,
   click Run. Status streams in real time.
2. **Report** — score, breakdown bars, prioritized recommendations
   (each with Effort/Impact/Priority badges), and collapsible
   specialist accordions for visual / UX / accessibility / brand /
   market.
3. **References** — top section auto-fills with what the brand and
   market agents actually consulted on this run; bottom section is a
   free-form search box that hits LanceDB + live web (Tavily/DDG) +
   editorial fallback in parallel.
4. **Settings** — three cards. Configuration (12 rows tagged `.env`/
   `code`/`auto`), live cost telemetry (auto-refreshes after every
   Run), and the tool registry (every LangChain `@tool` we ship).

In the Logs tab you'll see two key lines after every run:

```text
RUN START session=<id> frames=N mode=fake|real labels=...
RUN END   session=<id> run_id=<id> score=X.X tokens=N usd=$.$$$$
```

You can grep the rolling log by session id to slice one run from many.

---

## Common problems and how to fix them

| Problem | What to do |
| --- | --- |
| **`make hf-push` says "ERROR: HF_TOKEN env var is not set"** | You haven't run `export HF_TOKEN=hf_...` in this terminal yet. Run it again with your real token. |
| **`make hf-push` says "ERROR: 'hf' remote is not configured"** | You skipped Step 3b. Run `make hf-remote HF_USER=... HF_SPACE=...` first. |
| **HF Space build log shows `ModuleNotFoundError: ui`** | The `app.py` at the repo root is missing or wrong. Confirm with `ls app.py` and that it contains `from ui.app import main`. |
| **Build times out at 10 minutes** | First build only — be patient. PyTorch + open_clip wheels take a long time. Re-runs are 90 seconds. |
| **Space shows a blank page after build "succeeds"** | Server bound to the wrong address. Already fixed — `ui/app.py` auto-detects HF. If a fork removed the detection, the fix is in the `main()` function (3-tier `server_name` resolution). |
| **App starts but `OPENROUTER_API_KEY` errors when you click Run** | Secret not set. Go to Step 5 above, double-check the spelling of the secret name, then **Restart Space**. |
| **You see "Cost: $0.00" in the Settings tab but expected non-zero** | You're in offline-fakes mode (no OpenRouter key, or `USE_REAL` not set). That's intentional — fakes are free. Add the key + variable in Step 5 to switch. |
| **Visual section says "not captured" with a blue note** | The vision model returned a thin response and the self-heal retry didn't fully recover. Re-run, or switch `DEFAULT_VISION_MODEL` to `openai/gpt-5` or `anthropic/claude-3.5-sonnet` (more expensive but stronger vision). |
| **`OpenRouter returned empty content for X` errors on every agent** | GPT-5 / o1 / o3 are reasoning models — they spend a slice of `max_tokens` on hidden chain-of-thought BEFORE the visible JSON. The client auto-pins `reasoning.effort=minimal` and bumps `max_tokens` to 8192 for these families. If you still see empties, raise `DEFAULT_MAX_TOKENS=16384` or switch to `anthropic/claude-3.5-haiku` (non-reasoning, vision-capable, $0.80/$4.00 per 1M tokens). |
| **`Invalid JSON: EOF while parsing a string at line N column M`** | Same root cause as above — the reasoning-model token budget ran out mid-output. Same fixes apply. |
| **Quota / rate-limit errors from OpenRouter** | Free OpenRouter tier exhausted. Top up at <https://openrouter.ai/credits>, or remove the `USE_REAL` variable to fall back to fakes. |
| **References tab is empty after a Run** | No reference images committed. The "Empty brand-RAG corpus" message tells you to add images to `data/reference/` and run `make ingest`. The bottom search panel still works even with empty corpus (editorial fallback). |
| **Logs tab is unreadable after many runs** | Each run is bracketed by `RUN START session=<id>` / `RUN END session=<id>`. Use the search box in the Logs tab to grep by session id and see one run at a time. |

---

## Need to start fresh?

If your Space is in a weird state and you want a clean slate:

1. On your laptop: `make clean-runs` to wipe `data/reports/` and
   `data/logs/`. Add `CLEAN_CACHE=1` to also nuke the response cache.
2. Push again with `make hf-push` — Hugging Face replaces everything
   on push, no need to delete the Space.

If your Space build cache is stuck (rare), in the HF browser tab go
to **Settings → Factory reboot** to invalidate the build cache.

---

## I'm stuck — where do I get help?

- For build / deploy questions specific to Hugging Face:
  <https://discuss.huggingface.co/c/spaces/24>.
- For OpenRouter / model / billing questions:
  <https://openrouter.ai/docs>.
- For errors that look like Python tracebacks: copy the **last 30
  lines of the Logs tab** and ask in our project's discussion channel.

The deploy itself is straightforward — most failures fall into the
table above. If something doesn't match, the Logs tab on your Space
is always the source of truth.
