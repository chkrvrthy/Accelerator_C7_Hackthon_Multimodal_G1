# Demo Script — Multimodal AI Design Analysis Suite

> **Length:** 4 minutes target (3:30 minimum, 5:00 hard cap).
> **Speaker:** one team representative, screen-sharing the Gradio UI on
> `http://127.0.0.1:7860/`.
> **Goal:** maximize all three rubric points — Concept Score, Difficulty, Code
> Quality — in that order, because Concept Score is what we have the most of
> and what unlocks the other two.

---

## Pre-flight checklist (T-5 minutes)

1. **Fresh state** — run `make clean-runs` to wipe `data/reports/*` and
   `data/logs/*`. The Settings tab will then show zero accumulated
   reports and the log file starts empty so judges only see *this*
   demo's events. Cache is preserved (re-runs stay instant). Add
   `CLEAN_CACHE=1` to also wipe the response cache.
2. `make ingest` — confirm reference index has rows. If empty, the
   References tab top section will say *"Empty brand-RAG corpus. Drop
   a few reference images into data/reference/ and run `make ingest`"*.
3. `python ui/app.py` — wait for two lines:
   - `* Running on local URL: http://127.0.0.1:7860`
   - `* Logs are tee'd to: <path>/data/logs/app.log` ← copy this; you'll `tail -f` it.
4. Open the URL in a clean browser window. Zoom level 100%. Close DevTools.
5. Pre-stage the bundled sample: in **Analyze**, click the
   "Try the bundled sample (one-click prefill)" row so the file picker
   is already filled. Do **not** click Run yet.
6. **Decide mode** — set in `.env`, NOT in the UI (the UI has no toggle).
   - Real APIs: `USE_REAL=true` and `OPENROUTER_API_KEY=sk-or-...` in `.env`.
     ~25 s per run, ~$0.03 (single frame); ~$0.05 (3 frames); ~$0.08 (5 frames).
   - Offline fakes: `USE_REAL=false` (or simply omit the flag). Returns in
     <1 s, $0. **Recommended for live demo unless your network and
     OpenRouter key are both rock solid.**
   - The Analyze tab shows the active mode under the Run button as
     "_Mode is read from `.env` — currently **real APIs** / **offline fakes**_".
   - The Settings tab confirms `USE_REAL` and `OPENROUTER_API_KEY` are loaded.
7. Keep a terminal visible with `tail -f data/logs/app.log` (path from
   step 3). With real APIs on, judges see LangSmith trace IDs land;
   with fakes on, they see the per-agent INFO lines. Each run is
   bracketed by `RUN START session=<id>` / `RUN END session=<id>` so
   you can `grep "RUN START" data/logs/app.log` to count runs.
8. Have `docs/walkthrough.html` open in a second tab as a fallback. If
   the live demo dies, share that tab and narrate from the diagram.

---

## Step-by-step worked example (exactly what to click and type)

This is the literal click path for a clean demo. Copy-paste the exact strings.

### A. Boot the app (one terminal)

```bash
cd <path-to>/ai_c7_hackathon
# 1) Build (or refresh) the reference index — populates LanceDB so References
#    tab has thumbnails to show.
make ingest
# Expected output ends with a line like:
#   ingested N images into table 'design_references' (dim=512)

# 2) Launch the UI.
make ui
# Expected output:
#   * Running on local URL:  http://127.0.0.1:7860
#   * To create a public link, set `share=True` in `launch()`.
```

Open `http://127.0.0.1:7860` in your browser.

### B. (Optional) start the MCP server in a second terminal

Only needed if you plan to demo the MCP wow-moment at 3:15.

```bash
cd <path-to>/ai_c7_hackathon
make mcp
# Expected: a stdio MCP server starts and waits for an MCP client to attach.
# Leave this terminal visible on screen.
```

---

### C. Capture the demo screenshot — exact website

We're analyzing a real, recognizable website. **Use Stripe's payments
landing page** — it's the gold-standard fintech design, judges will know
it on sight, and it gives every specialist agent rich signal:

- **Visual agent** — strong gradients, hierarchy, generous whitespace.
- **UX agent** — clear primary CTA ("Start now"), short headline, social
  proof block, code sample for a developer audience.
- **Accessibility agent** — Stripe is WCAG 2.1 AA compliant, so the agent
  will report mostly passes (good — the demo doesn't get bogged down in
  red flags).
- **Brand agent** — purple/indigo gradient is unmistakable Stripe brand.
- **Market agent** — "Stripe payments" returns ~50 high-quality web hits.

#### C.1. Open the page

```text
URL:    https://stripe.com/payments
Screen: 1440 × 900 (laptop default), zoom 100%, dark mode OFF, ad-blockers OFF
Wait:   the hero gradient must be fully animated in (~2 s) before capture
```

#### C.2. Take a full-page PNG

| Platform | One-line capture                                                                                                 |
| -------- | ---------------------------------------------------------------------------------------------------------------- |
| macOS    | Press `Cmd+Shift+4`, then `Spacebar`, then click the browser window. PNG saved to `~/Desktop/`.                  |
| Linux    | Run `gnome-screenshot -w -d 2 -f ~/Desktop/stripe-payments.png` (waits 2 s, captures active window).             |
| Windows  | Press `Win+Shift+S`, drag a rectangle around the browser viewport, paste into Paint, save as PNG to `Desktop\`.  |
| Browser  | Chrome DevTools → `Cmd/Ctrl+Shift+P` → type `Capture full size screenshot` → Enter. PNG downloads automatically. |

Rename the file to **`stripe-payments.png`** and move it somewhere
predictable, e.g. `~/Desktop/stripe-payments.png`.

> **Why a real website and not the bundled `sample.png`?** The bundled
> sample is 82 bytes — it's a shape placeholder, not a designed screen.
> Judges want to see the agents critique a real page; a real page also
> makes the Effort/Impact tags meaningful.

#### C.3. (Fallback websites if Stripe is geo-blocked or the page changed)

Pick one in this order. They are all live, recognizable, and give all five
agents enough signal:

1. `https://www.notion.so` — content-design polish, accessibility passes.
2. `https://linear.app` — minimalist, dense product UI, dark gradients.
3. `https://www.figma.com/pricing` — pricing-page archetype, table layout.
4. `https://www.airbnb.com` — heavily researched UX, clear hierarchy.
5. `https://razorpay.com` — Indian fintech, if you want a regional angle.

---

### D. Tab 1 — **Analyze** (where you start the run)

The Analyze tab is the only tab that produces work. The other three tabs
read state. Give it 90 seconds of attention.

#### D.1. What's on the tab (top to bottom)

| Element                       | What it does                                                                                                                |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Hero band                     | Rubric-friendly title + the five capability chips (Visual / UX / Accessibility / Brand / Market). Read aloud once.          |
| Steps strip                   | Visual reminder of the flow (Upload → Add context → Review). Don't click — narrative scaffolding.                           |
| **Design screenshots**        | File upload — **1 to 5** PNG/JPG/WEBP, drag-and-drop or click-to-browse. Multiple files = comparison mode.                  |
| **Frame labels**              | Optional textbox, one label per line in upload order. Hover the `info` icon for syntax. Missing → filename stem fallback.   |
| **Context**                   | Free-text notes: audience, brand, goal, market. **Every word here is fed to all five agents** — concrete words win.         |
| Mode banner                   | One-line italic under Run, shows whether `.env` has real APIs or fakes active. Switch by editing `.env`, not the UI.        |
| `<details>` "How to upload"   | Collapsed by default. Expand for upload limits + preflight rules. Do NOT pre-expand for judges — the run is the demo.       |
| **Run analysis** (button)     | Kicks off the LangGraph DAG. Streams status back into the page. Use ONCE per query.                                         |
| Quickstart prefill markdown   | One-line caption above the Examples row: *"Click the row below to fill the form with a bundled demo screenshot."*           |
| **Try the bundled sample** row| Auto-fills the form with `src/fakes/fixtures/sample.png` + a "Sample dashboard" label + a default context. **Quickstart only — clear it before running on real designs.** |
| Status / log surface          | Renders "Ready" → "Analysis running" → "Report ready" inline as the run progresses.                                         |
| Raw structured report (accordion)| Collapsed accordion below the run button. Expand only if a judge says "show me the raw JSON".                            |

> **Single-frame vs comparison mode (multi-frame)** — the Analyze tab
> handles both with the same controls. Drop one screenshot for a fast
> single-screen review; drop 2–5 of the same product (Hero, Pricing,
> Dashboard, …) and the synthesizer correlates findings across screens
> and emits a per-frame heatmap with `affected_frames` badges on every
> recommendation. The 5-frame ceiling is enforced by the upload
> preflight — try a 6th and you get a friendly banner, no token spend.

#### D.2. Exact values to fill

**Single-frame demo (default — use this unless you've practiced multi-frame):**

1. **Design screenshots** — drag `~/Desktop/stripe-payments.png` from
   step C into the upload area. Wait until the file name appears.
2. **Frame labels** — leave blank. Filename stem (`stripe-payments`)
   becomes the label automatically.
3. **Context** — paste this exact text. It is engineered so each of the
   five specialists has at least one concrete keyword to react to:

   ```text
   Audience: SaaS builders and small e-commerce founders evaluating payment APIs.
   Brand: developer-credible, polished, modern, slightly playful, trustworthy.
   Goal: convert a first-time visitor into a "Start now" or "Contact sales" click.
   Constraint: WCAG 2.1 AA contrast, mobile-first, dark-mode friendly.
   Market: competing with Adyen, Square, Razorpay, and PayPal Braintree.
   ```

4. **Mode** — already set in `.env` (see pre-flight step 6). The banner
   under Run shows the active mode; for the live demo prefer **offline
   fakes** (`USE_REAL=false`) unless you've smoke-tested OpenRouter in
   the last 30 min.
5. Click **Run analysis** once.

**Multi-frame demo (3 screenshots of the same product — only if rehearsed):**

1. **Design screenshots** — drag THREE files in order:
   `stripe-home.png`, `stripe-pricing.png`, `stripe-checkout.png`.
   Capture them per step C; same screen size + zoom.
2. **Frame labels** — paste this in the labels textbox, one per line:

   ```text
   Home
   Pricing
   Checkout
   ```

3. **Context** — same paragraph as above (works for both modes).
4. Click **Run analysis** once. The status will read
   *"Reviewing 3 frames as one product with offline fakes: Home, Pricing, Checkout."*

#### D.3. What you should see

Status messages stream in below the form, in this order:

```text
Analysis running
Reviewing stripe-payments with offline fakes.        ← or "real APIs (.env)"

Report ready
Score: 76.4/100 across 1 frame. Tokens used: 22,100 (~$0.0066);
cache hits: 0. Open Report.
```

Each agent also logs to your terminal **AND** to `data/logs/app.log`. Point
judges at either. The pattern looks like this:

```text
2026-06-14 15:00:19.123 | INFO     | ui.handlers:on_run:148      - RUN START session=a6490c34 frames=1 mode=fake labels=stripe-payments
2026-06-14 15:00:19.450 | INFO     | src.agents.base:run_with_schema:140 - agent.visual: starting (schema=VisualAnalysis, images=1)
2026-06-14 15:00:19.612 | INFO     | src.agents.base:run_with_schema:156 - agent.visual: ok (VisualAnalysis)
...
2026-06-14 15:00:23.842 | INFO     | src.agents.synthesizer:run:316 - synthesizer: wrote design_report_2026-06-14T15-00-23+00-00_4794cd74.json (score=76.4, recs=3, status={...})
2026-06-14 15:00:23.844 | INFO     | ui.handlers:on_run:189      - RUN END session=a6490c34 run_id=4794cd74 score=76.4 tokens=22100 usd=0.0066
```

Every run is bracketed by `RUN START` / `RUN END` lines with a shared
`session=<id>`. To grep one specific run from a long-running log:

```bash
grep "session=a6490c34" data/logs/app.log
```

> **If you see `agent.visual: shallow response (palette-only). Retrying once...`**
> followed by `agent.visual: retry recovered the narrative.` — that's the
> visual self-heal loop firing. Keep narrating; the retry is invisible to
> the user and only doubles cost on the broken visual call. (See FAQ §6.5
> for the full story; mention it only if a judge asks.)

---

### E. Tab 2 — **Report** (the money shot)

The Report tab is where judges spend the most time. **Click it the moment
the score appears in the status bar.**

#### E.1. Reading the report top-to-bottom

1. **Title** — "Design report" with subtitle "Synthesized from five
   specialist agents." This is the synthesizer's signature.
2. **(Sometimes) "Review needed" banner** — a yellow/orange band that
   only appears when the quality gate flagged content-thin output (e.g.
   a missing executive summary, an empty visual narrative, a
   rec without `proof`). The banner shows up to 5 flagged fields with
   `field` paths like `visual.narrative` or `top_recommendations[*].affected_frames`.
   Click the **"What does this mean?"** disclosure to read the
   plain-English explainer (Review needed → Provisional numbers → How
   to fix). For the Stripe demo with real APIs you should NOT see this
   banner; if it appears, narrate honestly: *"the gate flagged
   `visual.narrative` because the model returned a shallow response;
   the self-heal retry didn't fully recover. The score is provisional,
   not gospel."* Then keep going — the rest of the report still renders.
3. **Score block** — 44 px green pill. Stripe should land in the **70–82**
   range. If it's <50 or >95, flag it as suspicious and check the agents
   didn't get a placeholder image.
4. **Score rationale** — one paragraph the synthesizer composes
   explaining where points were lost.
5. **Score breakdown bars** — five horizontal bars (visual / ux /
   accessibility / brand / market). Color-coded by score band.
6. **Per-frame heatmap** — only renders for multi-frame runs. One
   row per frame label, columns matching the breakdown bars. This is
   the "comparison mode" payoff — judges see "Pricing scored 65 on
   accessibility but Checkout scored 40" without reading prose.
7. **Top strengths** — 3–5 bullets. For Stripe, expect things like
   "consistent indigo→purple gradient", "clear primary CTA", "dense
   social proof above the fold".
8. **Prioritized recommendations** — 3 cards. Each card has:
   - **Priority** badge (1–5, 1 is most important).
   - **Title** (one short sentence).
   - **Effort** pill (gold) — values 1 (small fix) to 5 (major rework).
   - **Impact** pill (teal) — values 1 (cosmetic) to 5 (conversion-moving).
   - **Metric lift** chip (grey) — projected outcome, e.g. *"+15% CTR
     (similar tests)"*. May be `null` (target — set after a/b test).
   - **Affected frames** chips — only on multi-frame runs.
   - **Rationale** sentence + **Proof** citation (e.g. `accessibility:1.4.3`).
   The synthesizer ranks by `impact / effort`, so card 1 is the best
   bang-for-buck. Read card 1 aloud word-for-word.
9. **Specialist accordions** (collapsed by default — expand only if a
   judge asks). Five `<details>` blocks: Visual / UX / Accessibility /
   Brand / Market. The Visual accordion will show *"Layout: <i>not
   captured</i>"* with a self-heal note if the model returned a
   palette-only response and the retry didn't recover.

#### E.2. What to say while pointing

> *"This whole block came from one screenshot and one paragraph of context.
> Five specialists ran in parallel — about 25 seconds end-to-end on real
> APIs — and the synthesizer ranked the recommendations by impact over
> effort. Look at card one: gold pill is effort, teal pill is impact, the
> rationale is grounded in the visual and brand findings, not made up."*

#### E.3. Empty state

If the tab says "No report yet", you haven't clicked Run, or the run
failed. Go back to Analyze, check the status block for the error, and
either fix or use the offline-fakes fallback.

---

### F. Tab 3 — **References** (proof RAG + live web are real, not theatre)

This tab proves the agents aren't hallucinating citations. The tab has
**two stacked sections**:

- **Top section (auto-fills after every run)** — references the brand
  agent and market agent actually consulted during the most recent
  Run. Brand thumbnails come from LanceDB (CLIP image RAG); market
  citations come from the URLs the market agent embedded in its
  `MarketResearch` output.
- **Bottom section (ad-hoc search)** — a free-form query box that
  hits the local CLIP index AND the live web (Tavily, DDG fallback)
  AND a hand-curated editorial fallback. Always returns *something*
  useful, even with an empty corpus and no API key.

#### F.1. What's on the tab

| Element                          | What it does                                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **References used in this run** card | Auto-populated. Brand-RAG thumbnails (when corpus is non-empty) + market-agent citations (URLs). Empty after a clean install: *"Empty brand-RAG corpus. Drop a few reference images into data/reference/ and run `make ingest`..."* |
| Run-references gallery           | Up to 12 thumbnails the brand agent retrieved. Each tile shows `<id> · <similarity>` and (multi-frame runs) `· matched <frame>,<frame>`.|
| Search box + Search button       | Submits a query to LanceDB (image RAG) AND Tavily/DuckDuckGo (web) AND the editorial fallback.                     |
| Search-results gallery           | Local thumbnails from your reference index for the typed query. Empty if no local index — that's fine, see below.  |
| **Similar references** card      | Status text — how many indexed rows, how many local files, which web provider returned the hits.                   |
| **Web references** card          | Up to 5 live web hits with title (link), snippet, and provider (Tavily or DuckDuckGo).                             |
| **Editorial fallback** card      | Hand-curated sources (Stripe, Baymard, Refactoring UI, Material 3, etc.). Shown when local OR web came back thin — never let the user stare at a blank tab. |

#### F.2. Exact query for the Stripe demo

Type this into the search box and press Enter:

```text
fintech payments landing page hero gradient
```

Why this query: it pulls visually-similar fintech landing pages from your
LanceDB index AND web articles about hero-gradient design patterns —
both of which are evidence the brand-consistency and market agents would
have used during the report run.

Alternative queries depending on the website you analyzed:

| Website analyzed | Recommended query                                |
| ---------------- | ------------------------------------------------ |
| stripe.com       | `fintech payments landing page hero gradient`    |
| notion.so        | `productivity tool landing page minimalist`      |
| linear.app       | `dark theme product landing dense ui`            |
| figma.com        | `pricing page tier comparison saas`              |
| airbnb.com       | `marketplace search hero photography`            |
| razorpay.com     | `india fintech payments mobile-first`            |

If a judge asks "show me similar to Stripe", type literally that:
**`sites similar to stripe`** — the editorial fallback row will surface
Stripe + Baymard + Material 3 cards even with a fully cold corpus.

#### F.3. What you should see

- **Top section** (after a Run): brand thumbnails + market URL list.
  If empty, the empty-state copy explains it ("empty brand-RAG corpus" /
  "off-domain run"); narrate: *"top section auto-fills from the agents'
  actual retrievals, so an empty section means we haven't ingested
  references on this machine — that's a one-command fix with `make
  ingest`."*
- **Search section gallery**: 4–12 thumbnails when the local CLIP index
  is populated. If empty, the Status card says *"No local CLIP index
  yet — searching the live web below."* You haven't broken anything.
- **Web references card**: 3–5 cards, each externally clickable. If
  Tavily is unset, header reads "Web references from DuckDuckGo" —
  that's the open-source fallback, and that's deliberate.
- **Editorial fallback card**: only renders when local OR web returned
  thin. Always has 4–6 hand-curated rows so the page never looks dead.

#### F.4. What to say while pointing

> *"The top section auto-fills from this run — these are exactly the
> references the brand and market agents looked at. The search box
> below hits three sources in parallel: image RAG over our CLIP-embedded
> LanceDB store, live web via Tavily with DuckDuckGo as the
> open-source fallback, and a hand-curated editorial layer that always
> renders so the tab is never empty. Together that's how the agents
> get their evidence — they cannot ship a citation that isn't in one
> of those layers."*

---

### G. Tab 4 — **Settings** (deployability + cost story in 30 seconds)

The Settings tab is read-only — it surfaces the runtime configuration so
judges can verify nothing is hard-coded. Every row carries one of three
**source badges** so reviewers know where to change the value:

- `.env` — edit `.env` and restart.
- `code` — edit `src/config.py` and restart (advanced).
- `auto` — computed at boot from disk; not user-editable.

#### G.1. What's on the tab

The tab has **three stacked cards**:

**Card 1 — Current configuration** (read-only):

| Row                          | Source | What it means                                                                                                  |
| ---------------------------- | ------ | -------------------------------------------------------------------------------------------------------------- |
| OPENROUTER_API_KEY loaded    | `.env` | `True` if set; `False` otherwise. Real-API demo requires `True`.                                               |
| USE_REAL                     | `.env` | `True` = real APIs; `False` = offline fakes.                                                                   |
| TAVILY_API_KEY loaded        | `.env` | Optional. Enables Tavily live-web search; `False` falls back to DuckDuckGo.                                    |
| Text model                   | `code` | The default text-only LLM (`openai/gpt-5-mini`). $0.25 / $2.00 per 1M tokens.                                  |
| Vision model                 | `code` | The default multimodal LLM (`openai/gpt-5-mini`). Override to `gpt-5-nano` (cheap) or `claude-3.5-sonnet` (strong) via `.env`. |
| Temperature                  | `code` | Kept low (0.2) for consistent JSON-schema output and high cache hit rate.                                      |
| Max tokens / call            | `code` | Caps per-call cost. Default 4096.                                                                              |
| Cache                        | `auto` | `enabled` / `DISABLED`. Shows the count of cached responses on disk.                                           |
| Local reference images       | `auto` | Files under `data/reference/`. If 0, run `make ingest` after seeding the dir.                                  |
| Indexed reference rows       | `auto` | Rows in the LanceDB `design_references` table. Should equal "Local reference images" after ingestion.          |
| Reports directory            | `auto` | Repo-relative path. Each run drops a `design_report_<ts>_<run_id>.json` here.                                  |
| **App log file**             | `auto` | Repo-relative path to `data/logs/app.log`. Every run appends here. 10 MB rotation, 5 backups. `LOG_TO_FILE=0` disables. |

**Card 2 — Cost telemetry** (auto-refreshes after every run):

- Total tokens
- Total estimated USD (cumulative across the session)
- Cache hit count
- Per-agent breakdown (one row per specialist, showing tokens + USD)

**Card 3 — Tool registry**:

- One row per LangChain `@tool`-decorated callable (web_search, brand_lookup, etc.)
- Shows the tool name + its docstring summary so reviewers can audit
  what each agent actually has hands on.

#### G.2. What to say while pointing

> *"Three cards. Top card is the deploy contract — eleven lines, every
> one of them tagged `.env`, `code`, or `auto` so a new operator knows
> where to change it. Middle card is the live cost ledger — it
> auto-refreshes after every Run, so judges can verify the per-agent
> token and USD numbers in real time. Bottom card is the tool registry —
> every LangChain `@tool` we ship, by name. The whole app deploys to
> Hugging Face Spaces for free; the FAQ documents the budget — under a
> dollar a day for hackathon traffic."*

---

### H. (Optional) MCP demo at 3:15

If you started `make mcp` in step B, switch to that terminal for one beat.

Spoken line:

> *"That terminal is the same agents exposed over MCP. Any MCP-compatible
> client — Claude Code, an internal IDE, anything — can `tools/list` and
> see `analyze_visual`, `audit_accessibility`, and so on. Same agents,
> two surfaces."*

You do **not** need a live MCP client connected — the running server is
proof enough. If a judge insists, point at `src/mcp/server.py` in the
file tree and at the `tools` list inside it.

---

### H.5. Report + log retention (for the "what's persisted" question)

Both reports AND logs are **persistent and timestamped — never
auto-deleted**. The user owns the cleanup.

| Artifact      | Where                                      | Filename pattern                                              | Cleanup                                  |
| ------------- | ------------------------------------------ | ------------------------------------------------------------- | ---------------------------------------- |
| JSON report   | `data/reports/`                            | `design_report_<ISO-timestamp>_<run_id>.json` (sortable)      | `make clean-runs`                        |
| Side-by-side composite | `data/reports/`                   | `_composite_<short-hash>.png` (only on multi-frame runs)      | `make clean-runs`                        |
| App log       | `data/logs/app.log`                        | Single rolling file, 10 MB rotation, 5 backups                | `make clean-runs`                        |
| Per-run boundary | inside `data/logs/app.log`              | Two lines per run: `RUN START session=<id> ...` / `RUN END session=<id> ...` | grep by `session=<id>` to slice           |
| Cache         | `data/cache/`                              | `<hash>.json` per cached LLM response                         | `make clean-runs CLEAN_CACHE=1` (opt-in) |

**No timestamped log files** — the rolling-file approach keeps cross-run
grep simple and prevents the `data/logs/` directory from filling up
with hundreds of small files. If you need a per-run log slice, use
`grep "session=<id>" data/logs/app.log`. Filename for reports is
ISO-8601 with `:` replaced by `-` (Windows-safe), so a directory
listing is naturally chronological:

```text
$ ls -1 data/reports/*.json
data/reports/design_report_2026-06-14T15-00-19+00-00_4794cd74.json
data/reports/design_report_2026-06-14T15-04-43+00-00_8de1c022.json
data/reports/design_report_2026-06-14T15-12-08+00-00_f7a9bd11.json
```

For a fresh demo: `make clean-runs` wipes reports + logs but **keeps
the cache** so re-runs are still instant. Add `CLEAN_CACHE=1` to
opt into a fully cold start.

### I. Close the demo

Return to the **Report** tab so the score is the last thing on screen,
then deliver the closing line at 3:50.

---

## Spoken script (with screen cues)

**Time markers are spoken-time. Keep transitions short — no dead air.**

### 0:00 – 0:25 — Hook & problem (25 s)

> "Hi, we're Group 1 — and this is the **Multimodal AI Design Analysis
> Suite**. The problem: every design review at a real company is the same
> meeting on loop. A designer ships a screen, four reviewers re-derive the
> same checklist — visual, UX, accessibility, brand, market — and a week
> later somebody finally writes a memo. We replaced that meeting with a
> multi-agent panel that takes one screenshot and ships a prioritized,
> evidence-backed report in under thirty seconds."

**[SCREEN]** Hero band visible — "Design Analysis Suite" with the five
chips (Visual / UX / Accessibility / Brand / Market). Pause one beat so the
judges read the chips.

---

### 0:25 – 1:00 — Architecture in one breath (35 s — concept-dense)

> "Architecturally it's a **LangGraph** DAG. The graph fans out to **five
> specialist agents in parallel** with `asyncio.gather`, each one grounded
> by **image RAG** over a **CLIP-embedded LanceDB index** of reference
> designs, plus **Tavily** web search for live market signals. Every agent
> calls **multimodal GPT-4o or Claude 3.5 Sonnet over OpenRouter** with a
> **JSON-schema-constrained Pydantic** response, and a synthesizer agent
> rolls the five outputs into one ranked report. The full run is **traced
> in LangSmith**, **disk-cached** so re-runs cost zero, and exposed as an
> **MCP server** — so Claude Code or any MCP-compatible IDE can use our
> agents as tools. That covers eleven of the accelerator concepts in one
> screenshot."

**[SCREEN]** Briefly hover over the **steps strip** (Upload → Add context →
Review). Don't click anything yet.

> *(If you have an extra ten seconds, also say: "and yes — image is sent
> directly to the LLM as a base64 data URL with EXIF correction and a 1024
> px max-side resize, not OCR-then-text. The vision model sees the pixels
> the user sees.")*

---

### 1:00 – 2:30 — Live demo (90 s)

**[SCREEN]** Click **Run analysis**.

> "I'll run it on the bundled fintech dashboard sample. Watch the status
> bar — every agent logs start, finish, and any retry. That's deliberate:
> when a teammate's call fails at 2 a.m., we don't want a silent hang."

**[SCREEN]** As the status changes, narrate over it:

> "Visual agent measures hierarchy and density. UX critiques task flow
> against Nielsen's heuristics. Accessibility runs a WCAG-style contrast
> and target-size check. Brand-consistency compares the screen against our
> indexed reference set in LanceDB. Market-research pulls live web signals.
> The synthesizer composes a ranked recommendation list with effort and
> impact tags."

**[SCREEN]** Click the **Report** tab the moment the score appears.

> "There's the score — 76.4 out of 100. Top strengths first, then
> prioritized recommendations as cards. Each one has an **Effort** tag in
> gold and an **Impact** tag in teal — that's the whole point of the
> synthesizer: it has to argue why a fix is worth the work."

**[SCREEN]** Click **References** tab. Type `fintech dashboard onboarding`,
hit Enter.

> "The References tab is image RAG plus live web. Local results come from
> our LanceDB vector store — these thumbnails are real screens we
> ingested. Live web results come from Tavily, free-tier-fallback to
> DuckDuckGo. Together that's how brand-consistency and market-research
> get their evidence — we don't let agents hallucinate citations."

**[SCREEN]** Click **Settings** tab.

> "Settings is the deployability story. Real-API key loaded, indexed
> reference rows, report directory — all from a single `.env` file. The
> whole app deploys to Hugging Face Spaces for free, which is in our FAQ."

---

### 2:30 – 3:15 — Difficulty + Code-quality proof (45 s)

**[SCREEN]** Switch to terminal. `cat tests/ -1 | head` or just run
`pytest -q` so judges see green.

> "On code quality: **88 tests pass**, ruff and black are clean across the
> repo, every module carries a standard `OWNER / CONCEPTS / CONSUMES /
> PROVIDES` header so a new teammate can read the dependency graph in
> thirty seconds. We use **dependency injection with Protocol classes**,
> so every agent has a deterministic **fake** alongside the real
> implementation — that's how we wrote five people's tests in parallel
> without anyone needing an OpenRouter key."

**[SCREEN]** Optional: open `docs/walkthrough.html` and scroll the
architecture diagram for one beat.

> "On difficulty: this is **multimodal vision**, structured output that
> survives schema drift via a JSON-mode fallback, parallel agent
> orchestration, retrieval-augmented generation, an MCP server, and a
> cost-aware disk cache — under thirty seconds end-to-end on a real run.
> One person could not have built this; five people on five branches did,
> integrated cleanly through Protocol-shaped seams."

---

### 3:15 – 3:50 — MCP wow-moment + close (35 s)

**[SCREEN]** Open a second terminal, run `make mcp` (or
`python -m src.mcp.server`).

> "And one last thing — because the agents are exposed as an MCP server,
> any MCP-compatible client like Claude Code can call our visual analysis
> as a tool. That means the same engine that powers this UI can sit
> *inside* an engineer's IDE while they ship a feature. It's the same
> agent code — we just changed the surface."

**[SCREEN]** Return to the Gradio Report tab so the score is the last
visual.

> "So — eleven accelerator concepts, multimodal end-to-end, eighty-eight
> green tests, deployable on Hugging Face for under a dollar a day, and
> the whole thing is open source. That's our submission. Thank you."

---

## Concept-count cheat sheet (memorize)

If a judge asks "which accelerator concepts did you use?", answer in this
order — every item is a thing they can verify in the repo:

1. **Multimodal LLMs** — `src/llm/multimodal.py`, GPT-4o / Claude vision.
2. **Structured output / JSON schema** — `src/schemas/outputs.py`,
   Pydantic v2 plus `response_format={"type":"json_schema", ...}`.
3. **AI Agents (multi-agent panel)** — `src/agents/*.py`, five specialists
   plus a synthesizer.
4. **Agent orchestration** — `src/agents/graph.py`, LangGraph DAG.
5. **Parallel async fan-out** — `asyncio.gather` in the graph node.
6. **Image RAG** — `src/rag/embedder.py` + `src/rag/vector_store.py`,
   CLIP-on-LanceDB.
7. **Web search tool** — `src/tools/web_search.py`, Tavily with
   DuckDuckGo fallback.
8. **Observability / tracing** — `src/utils/tracing.py`, LangSmith with a
   no-op fallback.
9. **Cost optimization** — `src/llm/cost.py`, disk-backed `@cached`
   decorator, image resize, temperature 0.2 for cache hit rate.
10. **Evaluation harness** — `src/evals/harness.py`, deterministic fakes,
    schema-validated regression checks.
11. **MCP server** — `src/mcp/server.py`, exposes the same agents to any
    MCP-compatible IDE.
12. **Open-source-only stack** — Gradio UI, LangChain, LangGraph,
    LanceDB, open_clip, Pillow, OpenCV, Pydantic. Full license audit in
    `docs/FAQ.md`.

---

## Backup lines if something breaks live

| Failure                           | Spoken recovery                                                                                                                                          |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OpenRouter rate-limit / 429       | "We hit a real-API rate limit — that's why we have offline fakes." Open `.env`, set `USE_REAL=false`, restart `make ui`, click Run again — fakes return in 1 s. |
| Gradio fails to load              | "Live demo is down — the architecture is the same; let me walk through `docs/walkthrough.html` instead." Switch to the HTML walkthrough tab.             |
| LanceDB shows zero indexed rows   | "References live-search needs `make ingest`. The Tavily side still works — let me show that path." Skip local thumbnails, narrate the web-results card.  |
| Tavily key missing                | "We fall back to DuckDuckGo automatically — no judge sees a blank page." Carry on; the search returns DDG hits.                                          |
| Schema validation error in report | "That's the eval harness catching a bad agent output — exactly what we built it for." Open the warning log and read the agent name + bad field.          |
| MCP server fails to bind          | "MCP runs in any compatible IDE; the binding is just for this laptop." Skip the live MCP step, point at `src/mcp/server.py` in the file tree.            |

---

## 5-minute extended cut (if judges ask for more)

After the standard close, add this 60-second appendix:

> "Two things we'd ship next. **First, an offline fallback model** — we
> already have a Hugging Face local-LLM stub at `src/llm/hf_local.py`, so
> a Qwen 2.5 0.5B can answer when there's no internet. Demo runs on a
> laptop. **Second, a model council** — right now every agent calls one
> model; the synthesizer is the council. The cleanest extension is to
> give each agent two models — GPT-4o and Claude — and have the
> synthesizer arbitrate disagreements. That's a one-week change because
> our LLM client is already a Protocol — you swap the implementation, not
> the agent. Both ideas are documented as TODOs in the per-person README
> files so the next cohort can pick them up."

---

## One-line elevator pitch (for the Q&A)

> "It's a multi-agent multimodal design reviewer. Five specialists run in
> parallel against image RAG and live web, a synthesizer ranks the fixes,
> and the whole thing is exposed both as a Gradio app and as an MCP server
> — so the same engine ships to designers and to engineers in their IDE."
