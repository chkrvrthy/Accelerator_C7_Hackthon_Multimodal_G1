# --------------------------------------------------------------------------
# Convenience targets for a 5-person hackathon team.
# Run `make help` for the menu. Default target prints help.
# --------------------------------------------------------------------------

.DEFAULT_GOAL := help

PY  ?= python
PIP ?= pip

.PHONY: help \
        venv install install-a install-b install-c install-d install-e \
        fmt lint todos clean clean-runs diagrams \
        test test-a test-b test-c test-d test-e test-real cov \
        run-a run-b run-c-visual run-c-brand run-d-ux run-d-a11y run-e-market \
        ui mcp ingest eval demo hf-remote hf-push

help:
	@echo "Bootstrap"
	@echo "  install            All slices + dev tools (one-stop)"
	@echo "  install-a..e       Only one slice + dev tools"
	@echo "Quality"
	@echo "  fmt                black + ruff --fix"
	@echo "  lint               ruff + mypy src"
	@echo "  todos              List TODO/FIXME markers across the repo"
	@echo "Tests"
	@echo "  test               All slices, fakes only (CI default)"
	@echo "  test-a..e          One slice + cross-cutting (schemas/contracts/fakes)"
	@echo "  test-real          Tests marked real_api (requires keys in .env)"
	@echo "  cov                Coverage across src/"
	@echo "Per-slice smoke runs (USE_REAL=1 swaps fakes for real impls)"
	@echo "  run-a              Full graph end-to-end against bundled sample"
	@echo "  run-b              Retriever query smoke (text)"
	@echo "  run-c-visual       Visual analysis on bundled sample"
	@echo "  run-c-brand        Brand consistency on bundled sample"
	@echo "  run-d-ux           UX critique on bundled sample"
	@echo "  run-d-a11y         Accessibility audit on bundled sample"
	@echo "  run-e-market       Market research on bundled sample"
	@echo "Demo / Apps"
	@echo "  ui                 Launch Gradio at http://127.0.0.1:7860"
	@echo "  mcp                Start stdio MCP server"
	@echo "  ingest             Ingest data/reference/* into LanceDB"
	@echo "  eval               Run the schema-validity eval harness"
	@echo "  diagrams           Re-render docs/images/*.png from scripts/render_diagrams.py"
	@echo "  demo               ingest + run-a + ui (one command)"
	@echo "  clean              Remove caches and build artifacts"
	@echo "  clean-runs         Wipe data/reports/* and data/logs/* (fresh demo state)"
	@echo "Hugging Face Spaces"
	@echo "  hf-remote          Wire up the 'hf' git remote (HF_USER + HF_SPACE required)"
	@echo "  hf-push            Push current branch to the 'hf' remote (triggers a Space rebuild)"

# ----- bootstrap ----------------------------------------------------------
install:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/all.txt

install-a:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/person-a-infra.txt

install-b:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/person-b-rag.txt

install-c:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/person-c-agents.txt

install-d:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/person-d-agents.txt

install-e:
	$(PIP) install -U pip wheel
	$(PIP) install -e ".[dev]" -r requirements/person-e-ui.txt

# ----- quality ------------------------------------------------------------
fmt:
	black .
	ruff check --fix .

lint:
	ruff check .
	mypy src

todos:
	@rg "^\s*# (TODO|FIXME)" src/ ui/ scripts/ tests/ || echo "No TODOs found."

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +

# Wipe the persistent run artifacts (timestamped reports, brand
# side-by-side composites, the rolling app log). Useful right before a
# fresh demo so the Settings tab shows zero accumulated state. The
# response cache is preserved on purpose — that's what makes a re-run
# feel instant. Pass CLEAN_CACHE=1 to nuke that too.
clean-runs:
	@echo "Wiping data/reports/* and data/logs/* ..."
	@rm -f data/reports/*.json data/reports/_composite_*.png
	@rm -f data/logs/*.log data/logs/*.log.*
	@if [ "$(CLEAN_CACHE)" = "1" ]; then \
	  echo "Also wiping data/cache/* (CLEAN_CACHE=1) ..."; \
	  rm -rf data/cache/*; \
	fi
	@echo "Done. Reports: $$(ls data/reports/ 2>/dev/null | wc -l), logs: $$(ls data/logs/ 2>/dev/null | wc -l)."

# ----- tests --------------------------------------------------------------
# CROSS = the cross-cutting tests every person also runs locally.
CROSS = tests/test_schemas.py tests/test_contracts.py tests/test_fakes.py

test:
	pytest -m "not real_api"

test-a:
	pytest tests/person_a $(CROSS) -m "not real_api"

test-b:
	pytest tests/person_b $(CROSS) -m "not real_api"

test-c:
	pytest tests/person_c $(CROSS) -m "not real_api"

test-d:
	pytest tests/person_d $(CROSS) -m "not real_api"

test-e:
	pytest tests/person_e $(CROSS) -m "not real_api"

test-real:
	pytest -m real_api

cov:
	pytest --cov=src --cov-report=term-missing -m "not real_api"

# ----- per-slice smoke runs ----------------------------------------------
SAMPLE ?= src/fakes/fixtures/sample.png

run-a:
	$(PY) -m src.agents.graph --image $(SAMPLE)

run-b:
	$(PY) -m src.rag.retriever --text "modern fintech dashboard" --k 5

run-c-visual:
	$(PY) -m src.agents.visual_analysis --image $(SAMPLE)

run-c-brand:
	$(PY) -m src.agents.brand_consistency --image $(SAMPLE)

run-d-ux:
	$(PY) -m src.agents.ux_critique --image $(SAMPLE)

run-d-a11y:
	$(PY) -m src.agents.accessibility --image $(SAMPLE)

run-e-market:
	$(PY) -m src.agents.market_research --image $(SAMPLE)

# ----- demo / apps --------------------------------------------------------
ui:
	$(PY) ui/app.py

mcp:
	$(PY) -m src.mcp.server

ingest:
	$(PY) -m scripts.ingest_references --source ./data/reference

eval:
	$(PY) -m scripts.run_evals

diagrams:
	$(PY) scripts/render_diagrams.py

demo: ingest run-a ui

# ----- Hugging Face Spaces deploy ----------------------------------------
# One-time wiring of the HF Spaces remote. Run once after creating the
# Space on huggingface.co/new-space:
#   make hf-remote HF_USER=<your-user> HF_SPACE=<space-name>
hf-remote:
	@if [ -z "$(HF_USER)" ] || [ -z "$(HF_SPACE)" ]; then \
	  echo "ERROR: pass HF_USER=<user> HF_SPACE=<space> on the command line."; \
	  echo "  Example: make hf-remote HF_USER=alice HF_SPACE=design-suite"; \
	  exit 1; \
	fi
	@if git remote get-url hf >/dev/null 2>&1; then \
	  echo "Updating existing 'hf' remote -> https://huggingface.co/spaces/$(HF_USER)/$(HF_SPACE)"; \
	  git remote set-url hf "https://huggingface.co/spaces/$(HF_USER)/$(HF_SPACE)"; \
	else \
	  echo "Adding 'hf' remote -> https://huggingface.co/spaces/$(HF_USER)/$(HF_SPACE)"; \
	  git remote add hf "https://huggingface.co/spaces/$(HF_USER)/$(HF_SPACE)"; \
	fi
	@git remote -v | grep '^hf'

# Push the current branch to the HF Spaces remote, which triggers a
# rebuild. Requires that you have already run ``make hf-remote`` once
# AND that ``HF_TOKEN`` (an HF write token from
# https://huggingface.co/settings/tokens) is exported in your shell.
# The token is consumed inline; we never write it to disk or .git/config.
hf-push:
	@if [ -z "$(HF_TOKEN)" ]; then \
	  echo "ERROR: HF_TOKEN env var is not set. Generate a write token at"; \
	  echo "  https://huggingface.co/settings/tokens"; \
	  echo "and export it (e.g. 'export HF_TOKEN=hf_...') before running this target."; \
	  exit 1; \
	fi
	@if ! git remote get-url hf >/dev/null 2>&1; then \
	  echo "ERROR: 'hf' remote is not configured. Run 'make hf-remote HF_USER=... HF_SPACE=...' first."; \
	  exit 1; \
	fi
	@URL=$$(git remote get-url hf); \
	HOST_PATH=$${URL#https://}; \
	echo "Pushing HEAD -> hf/main ..."; \
	git push "https://USER:$(HF_TOKEN)@$$HOST_PATH" HEAD:main 2>&1 | sed "s|$(HF_TOKEN)|***REDACTED***|g"
