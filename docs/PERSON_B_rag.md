# Person B — Image RAG

> **Mission.** You own retrieval. Brand consistency lives or dies on what you
> return. The judges score "Difficulty" partly because Image RAG is genuinely
> hard, and your slice is what makes it real.

## Why your slice exists (concepts you are demonstrating)

| Sprint | Concept | What you ship |
|---|---|---|
| 3 | Chunking + embeddings (CLIP) | `src/rag/embedder.py` |
| 3 | Vector DB (LanceDB) | `src/rag/vector_store.py` |
| 3 | Retrieval (k-NN, image- and text-query) | `src/rag/retriever.py` |
| 3 | LlamaIndex (concept claim) | one import line in `src/rag/retriever.py` |
| 5 | LangChain tool wrapper | `src/tools/rag_tool.py` |

The brand-consistency agent (Person C) is your only consumer. The UI (Person E,
Tab 3) and the MCP server (Person E) also call your `Retriever`. The seam is
the `Retriever` Protocol in `src/contracts.py` — code against that, not against
your concrete classes.

## Files you own

| File | One-line purpose |
|---|---|
| `src/rag/embedder.py` | CLIP image+text embeddings (same vector space). |
| `src/rag/vector_store.py` | LanceDB schema + open/upsert/query helpers. |
| `src/rag/retriever.py` | `LanceRetriever` implementing `Retriever`. |
| `src/rag/editorial_refs.py` | Hand-curated fallback when index + web search are empty. |
| `src/tools/image_utils.py` | Pillow helpers used by everyone. |
| `src/tools/rag_tool.py` | LangChain BaseTool wrapper (Sprint 5 concept). |
| `scripts/ingest_references.py` | CLI to populate LanceDB from `data/reference/`. |
| `tests/person_b/*`, `tests/test_editorial_refs.py` | Your test slice + the new fallback tests. |

## Architecture view

See `docs/ARCHITECTURE.md` ("Person B — Image RAG") and `docs/walkthrough.html`.

## Contracts you implement

```python
class Retriever(Protocol):
    def retrieve_by_image(self, image_path, k=5) -> list[RetrievedRef]: ...
    def retrieve_by_text(self, text, k=5) -> list[RetrievedRef]: ...
```

## Setup — first 5 minutes (do exactly this)

### 1. Clone and create a venv

**Linux / macOS:**

```bash
git clone <repo-url> ai_c7_hackathon && cd ai_c7_hackathon
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-b-rag.txt
```

**Windows (PowerShell):**

```powershell
git clone <repo-url> ai_c7_hackathon ; cd ai_c7_hackathon
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -U pip wheel
pip install -e ".[dev]" -r requirements/person-b-rag.txt
```

`person-b-rag.txt` pulls torch + open_clip_torch + lancedb + llama-index. The first install takes ~2-3 minutes. Drink coffee.

### 2. Keys you need

| Key | Mandatory for Person B? | Where to get it | Free tier? |
|---|---|---|---|
| `OPENROUTER_API_KEY` | **Optional** — only if you run the full graph end-to-end. Your slice (CLIP + LanceDB) doesn't call any LLM. | https://openrouter.ai/keys | Pay-as-you-go |

You can do 100% of your work (embedder, vector store, retriever, ingest CLI, RAGSearchTool) with **zero API keys**. Person C consumes your retriever; both of you can develop offline against the bundled `FakeRetriever`.

### 3. Copy and fill `.env`

```bash
# Linux / macOS:
cp .env.example .env

# Windows (PowerShell):
Copy-Item .env.example .env
```

**File to edit:** `./.env` (the file you just created at the repo root — NOT
`.env.example`, that's the template).

You don't have to edit **anything** for your own slice. CLIP + LanceDB run
fully offline. The defaults are fine.

If you want to run the full graph end-to-end (i.e. test that Person C's
brand agent actually consumes your retriever output), ask Person A for the
OpenRouter key and make exactly **two edits** in your `.env`:

| Line | Before (find this) | After (replace with) |
|---|---|---|
| L10 | `OPENROUTER_API_KEY=sk-or-v1-REPLACE_ME` | `OPENROUTER_API_KEY=sk-or-v1-<paste shared key>` |
| L65 | `USE_REAL=0` | `USE_REAL=1` |

Leave every other line as-is.

**Never commit `.env`.** It's already in `.gitignore`. Only `.env.example`
ships in git.

### 4. Verify your env + heavy deps loaded

```bash
python -c "import torch, open_clip, lancedb; print('torch:', torch.__version__); print('open_clip ok'); print('lancedb:', lancedb.__version__)"
```

If `torch` is the CPU build that's fine — CLIP runs on CPU just slower. GPU is a nice-to-have, not required.

### 5. First successful run

```bash
make test-b            # tests pass against fakes; once you implement embedder/store, the skipped tests run too

# After you implement embedder + vector_store + retriever:
mkdir -p data/reference && cp src/fakes/fixtures/sample.png data/reference/  # seed with anything
make ingest            # builds the LanceDB
python -m src.rag.retriever --text "modern fintech dashboard" --k 5
```

## Run-in-isolation

```
# 1. Drop 5 reference PNGs into data/reference/
make ingest                                            # builds LanceDB
python -m src.rag.retriever --text "modern fintech dashboard" --k 5
python -m src.rag.retriever --image data/reference/foo.png --k 5
```

## Smoke tests

```
make test-b
```

The CLIP / LanceDB tests skip automatically when those packages are missing;
once you `pip install -r requirements/person-b-rag.txt`, they run.

## Implementation hot-spots

1. **`src/rag/embedder.py:CLIPEmbedder.__init__`** — load model once, cache on
   the class so re-construction is free. Auto-pick `cuda` if available.
2. **`embed_image` / `embed_text`** — always L2-normalize so cosine similarity
   reduces to a dot product (LanceDB's `metric("cosine")` expects that).
3. **`src/rag/vector_store.py:get_or_create_table`** — pyarrow schema with
   `vector: pa.list_(pa.float32(), dim)`. Use `dim` from the embedder.
4. **`scripts/ingest_references.py:main`** — walk the corpus, embed in batches
   of 8-16, upsert. Skip files already ingested by SHA1 of bytes.

## Done when

- [ ] `make test-b` is green from a fresh `.venv`.
- [ ] `make ingest` populates LanceDB with at least 5 entries.
- [ ] `python -m src.rag.retriever --text "fintech dashboard"` returns ≥3
      hits with score > 0.2 against your seeded corpus.
- [ ] `RAGSearchTool._run("...")` returns valid JSON list of dicts.

## Common pitfalls

- **torch CPU vs CUDA** — pick one path, document it. CPU is the fallback.
- **EXIF rotation** — Pillow auto-rotates based on EXIF; CLIP's preprocess
  expects raw RGB. Strip EXIF before embedding for consistency between
  ingest-time and query-time.
- **LanceDB schema mismatch on re-ingest** — if you change `dim`, drop the
  table (`--clear`) before re-ingesting, otherwise you'll get a schema error.
- **Score scale** — LanceDB returns `_distance`; convert to similarity via
  `score = 1 - distance` so `score ∈ [0, 1]` matches `RetrievedRef.score`.
